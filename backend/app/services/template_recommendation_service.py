"""
Template Recommendation Service

This service provides:
- Intelligent template recommendation based on enterprise characteristics
- Industry-based matching
- Risk-based prioritization
- Historical effectiveness learning
"""

import json
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Integer
from sqlalchemy.orm import selectinload

from app.config import settings
from app.utils.llm_fallback import create_main_llm_client
from app.models.template import InspectionTemplate
from app.models.enterprise import Enterprise
from app.models.industry import Industry
from app.models.rag import TemplateRecommendation
from app.models.task import InspectionTask


RECOMMENDATION_PROMPT = """你是检查模板推荐专家。根据企业信息，推荐最适合的检查模板。

【企业信息】
- 名称：{enterprise_name}
- 行业：{industry_name}
- 企业类型：{enterprise_type}
- 经济类型：{economic_type}
- 风险等级：{risk_level}
- 从业人数：{employee_count}
- 主要产品：{products}
- 资质证书：{qualifications}

【可用模板】
{templates_info}

请分析企业特点，推荐1-3个最合适的检查模板。以JSON格式输出：
{{
    "recommendations": [
        {{
            "template_id": "模板ID",
            "score": 0.95,
            "reasons": ["原因1", "原因2"]
        }}
    ],
    "analysis": "企业特点分析"
}}
"""


class TemplateRecommendationService:
    """Service for intelligent template recommendation"""

    def __init__(self):
        self.client = create_main_llm_client()
        self.model = settings.LLM_MODEL

    async def recommend_templates(
        self,
        enterprise_id: str,
        db: AsyncSession,
        top_k: int = 3,
        use_ai: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Recommend templates for an enterprise.

        Args:
            enterprise_id: Enterprise ID
            db: Database session
            top_k: Number of recommendations to return
            use_ai: Whether to use AI for enhanced matching

        Returns:
            List of recommended templates with scores and reasons
        """
        # Fetch enterprise with related data
        result = await db.execute(
            select(Enterprise)
            .options(selectinload(Enterprise.products))
            .options(selectinload(Enterprise.qualifications))
            .options(selectinload(Enterprise.industry))
            .where(Enterprise.id == enterprise_id)
        )
        enterprise = result.scalar_one_or_none()

        if not enterprise:
            return []

        # Get available templates
        templates = await self._get_available_templates(db, enterprise)

        if not templates:
            return []

        # Calculate base scores using rules
        scored_templates = []
        for template in templates:
            score, reasons = self._calculate_base_score(enterprise, template)
            scored_templates.append({
                "template": template,
                "score": score,
                "reasons": reasons,
            })

        # Sort by score
        scored_templates.sort(key=lambda x: x["score"], reverse=True)

        # Use AI for enhanced matching if requested
        if use_ai and len(scored_templates) > 0:
            try:
                ai_recommendations = await self._ai_enhanced_matching(
                    enterprise, scored_templates[:min(10, len(scored_templates))]
                )
                # Merge AI scores with base scores
                for ai_rec in ai_recommendations:
                    for st in scored_templates:
                        if str(st["template"].id) == ai_rec.get("template_id"):
                            # Weighted combination
                            st["score"] = st["score"] * 0.4 + ai_rec.get("score", 0) * 0.6
                            st["reasons"].extend(ai_rec.get("reasons", []))
                            break
                # Re-sort after AI enhancement
                scored_templates.sort(key=lambda x: x["score"], reverse=True)
            except Exception as e:
                print(f"[Recommendation] AI enhancement failed: {e}")

        # Return top_k recommendations
        recommendations = []
        for item in scored_templates[:top_k]:
            recommendations.append({
                "template_id": str(item["template"].id),
                "template_name": item["template"].name,
                "template_code": item["template"].code,
                "category": item["template"].category,
                "score": item["score"],
                "reasons": item["reasons"],
            })

        return recommendations

    async def _get_available_templates(
        self,
        db: AsyncSession,
        enterprise: Enterprise,
    ) -> List[InspectionTemplate]:
        """Get templates available for recommendation."""
        stmt = select(InspectionTemplate).where(
            InspectionTemplate.is_published == True
        )

        # Filter by industry if available
        if enterprise.industry_id:
            stmt = stmt.where(
                (InspectionTemplate.industry_id == enterprise.industry_id) |
                (InspectionTemplate.industry_id == None)  # General templates
            )

        result = await db.execute(stmt)
        return result.scalars().all()

    def _calculate_base_score(
        self,
        enterprise: Enterprise,
        template: InspectionTemplate,
    ) -> tuple[float, List[str]]:
        """Calculate base recommendation score using rules."""
        score = 0.5  # Base score
        reasons = []

        # Industry match (highest weight)
        if enterprise.industry_id and template.industry_id:
            if enterprise.industry_id == template.industry_id:
                score += 0.3
                reasons.append("行业匹配")

        # Category match
        if template.category:
            enterprise_type = enterprise.enterprise_type or ""
            if template.category.lower() in enterprise_type.lower():
                score += 0.1
                reasons.append("企业类型匹配")

        # Risk level consideration
        risk_level = enterprise.risk_level or "B"
        if risk_level in ["A", "高风险"]:
            # High-risk enterprises need more comprehensive templates
            if template.description and "全面" in template.description:
                score += 0.1
                reasons.append("适合高风险企业全面检查")

        # Historical effectiveness
        # This would require querying historical data

        return min(score, 1.0), reasons

    async def _ai_enhanced_matching(
        self,
        enterprise: Enterprise,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Use AI to enhance template matching."""
        # Prepare enterprise info
        products = [p.name for p in enterprise.products] if enterprise.products else []
        qualifications = [q.qual_type for q in enterprise.qualifications] if enterprise.qualifications else []

        # Prepare templates info
        templates_info = []
        for item in candidates:
            template = item["template"]
            templates_info.append(
                f"- ID: {template.id}, 名称: {template.name}, "
                f"类别: {template.category or '通用'}, "
                f"描述: {template.description or '无'}"
            )

        prompt = RECOMMENDATION_PROMPT.format(
            enterprise_name=enterprise.name,
            industry_name=enterprise.industry.name if enterprise.industry else "未指定",
            enterprise_type=enterprise.enterprise_type or "未指定",
            economic_type=enterprise.economic_type or "未指定",
            risk_level=enterprise.risk_level or "未指定",
            employee_count=enterprise.employee_count or "未知",
            products=", ".join(products[:5]) or "无",
            qualifications=", ".join(qualifications[:5]) or "无",
            templates_info="\n".join(templates_info),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )

            content = response.choices[0].message.content or ""
            return self._parse_ai_response(content)

        except Exception as e:
            print(f"[Recommendation] AI matching error: {e}")
            return []

    def _parse_ai_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response into recommendations."""
        from app.utils.llm_json import extract_json

        recommendations = []
        try:
            parsed = extract_json(response)
        except ValueError:
            return recommendations
        if isinstance(parsed, dict):
            recommendations = parsed.get("recommendations", []) or []
        elif isinstance(parsed, list):
            recommendations = parsed
        return recommendations

    async def record_recommendation_feedback(
        self,
        enterprise_id: str,
        template_id: str,
        was_accepted: bool,
        was_effective: Optional[bool],
        user_id: str,
        db: AsyncSession,
    ) -> None:
        """Record feedback on a recommendation for learning."""
        recommendation = TemplateRecommendation(
            enterprise_id=enterprise_id,
            template_id=template_id,
            was_accepted=was_accepted,
            was_effective=was_effective,
            created_by=user_id,
        )
        db.add(recommendation)
        await db.commit()

    async def get_popular_templates(
        self,
        db: AsyncSession,
        industry_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get most frequently used templates."""
        # Query task counts by template（模板与任务都排除软删除，已删任务不该撑高热度）
        stmt = (
            select(
                InspectionTemplate,
                func.count(InspectionTask.id).label("usage_count")
            )
            .outerjoin(
                InspectionTask,
                (InspectionTask.template_id == InspectionTemplate.id)
                & (InspectionTask.is_deleted == False),  # noqa: E712
            )
            .where(
                InspectionTemplate.is_published == True,
                InspectionTemplate.is_deleted == False,  # noqa: E712
            )
            .group_by(InspectionTemplate.id)
            .order_by(func.count(InspectionTask.id).desc())
            .limit(limit)
        )

        if industry_id:
            stmt = stmt.where(InspectionTemplate.industry_id == industry_id)

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "template_id": str(row[0].id),
                "template_name": row[0].name,
                "category": row[0].category,
                "usage_count": row[1],
            }
            for row in rows
        ]

    async def get_template_effectiveness(
        self,
        template_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get effectiveness metrics for a template."""
        result = await db.execute(
            select(
                func.count(TemplateRecommendation.id).label("total_recommendations"),
                func.sum(
                    func.cast(TemplateRecommendation.was_accepted, Integer)
                ).label("accepted_count"),
                func.sum(
                    func.cast(TemplateRecommendation.was_effective, Integer)
                ).label("effective_count"),
            ).where(TemplateRecommendation.template_id == template_id)
        )
        row = result.one()

        total = row[0] or 0
        accepted = row[1] or 0
        effective = row[2] or 0

        return {
            "template_id": template_id,
            "total_recommendations": total,
            "acceptance_rate": accepted / total if total > 0 else 0,
            "effectiveness_rate": effective / accepted if accepted > 0 else 0,
        }


template_recommendation_service = TemplateRecommendationService()