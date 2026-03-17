"""
Multimodal Service for Photo Analysis

This service provides:
- Photo content analysis using vision-capable LLM
- Compliance detection from images
- Automatic issue identification
"""

import base64
import json
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.media import MediaFile
from app.models.rag import PhotoAnalysis


PHOTO_ANALYSIS_PROMPT = """你是一位专业的现场检查员助手。请分析这张检查照片，识别可能存在的问题或不合规情况。

分析要求：
1. 描述照片中看到的主要内容
2. 识别任何安全、合规或质量问题
3. 如果发现问题，说明具体违反了什么标准或规范
4. 给出改进建议

请以JSON格式输出分析结果：
{
    "description": "照片内容描述",
    "issues": [
        {
            "type": "问题类型（safety/quality/compliance/other）",
            "severity": "严重程度（high/medium/low）",
            "description": "问题描述",
            "location": "问题位置（如果能识别）"
        }
    ],
    "compliance_status": "compliant/non_compliant/warning",
    "confidence": 0.8,
    "recommendations": [
        "建议1",
        "建议2"
    ]
}

如果照片内容无法判断或与检查无关，请说明。
"""


class MultimodalService:
    """Service for photo analysis using vision-capable LLM"""

    def __init__(self):
        # Use dedicated vision LLM client (Qwen3.5 Plus supports multimodal)
        self.client = AsyncOpenAI(
            base_url=settings.VISION_LLM_BASE_URL,
            api_key=settings.VISION_LLM_API_KEY,
            timeout=180,
        )
        self.vision_model = settings.VISION_LLM_MODEL

    async def analyze_photo(
        self,
        media_file_id: str,
        db: AsyncSession,
        analysis_type: str = "compliance",
        task_item_id: Optional[str] = None,
        check_item_title: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a photo using vision LLM.

        Args:
            media_file_id: ID of the media file to analyze
            db: Database session
            analysis_type: Type of analysis (compliance, safety, quality, general)
            task_item_id: Associated task item record ID
            check_item_title: Title of the check item for context
            custom_prompt: Custom analysis prompt

        Returns:
            Analysis results
        """
        # Fetch media file
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == media_file_id)
        )
        media_file = result.scalar_one_or_none()

        if not media_file:
            return {"error": "Media file not found"}

        if media_file.file_type != "image":
            return {"error": "Only image files can be analyzed"}

        # Read and encode image
        try:
            image_base64 = self._read_and_encode_image(media_file.file_path)
        except Exception as e:
            return {"error": f"Failed to read image: {str(e)}"}

        # Build prompt
        prompt = custom_prompt or PHOTO_ANALYSIS_PROMPT
        if check_item_title:
            prompt = f"检查项：{check_item_title}\n\n{prompt}"

        # Call vision API
        start_time = time.time()
        try:
            response = await self._call_vision_api(prompt, image_base64)
            analysis_result = self._parse_analysis_response(response)
            duration_ms = int((time.time() - start_time) * 1000)
        except Exception as e:
            print(f"[Multimodal] Vision API error: {e}")
            return {"error": f"Vision analysis failed: {str(e)}"}

        # Save analysis to database
        photo_analysis = PhotoAnalysis(
            media_file_id=media_file_id,
            task_item_id=task_item_id,
            analysis_type=analysis_type,
            detected_issues=json.dumps(analysis_result.get("issues", []), ensure_ascii=False),
            compliance_status=analysis_result.get("compliance_status"),
            confidence_score=analysis_result.get("confidence", 0.5),
            analysis_result=analysis_result.get("description", ""),
            recommendations=json.dumps(analysis_result.get("recommendations", []), ensure_ascii=False),
            model_used=self.vision_model,
        )
        db.add(photo_analysis)
        await db.commit()
        await db.refresh(photo_analysis)

        return {
            "id": str(photo_analysis.id),
            "media_file_id": str(media_file_id),
            "analysis_type": analysis_type,
            "description": analysis_result.get("description", ""),
            "issues": analysis_result.get("issues", []),
            "compliance_status": analysis_result.get("compliance_status"),
            "confidence": analysis_result.get("confidence", 0.5),
            "recommendations": analysis_result.get("recommendations", []),
            "model_used": self.vision_model,
            "duration_ms": duration_ms,
        }

    async def analyze_photo_stream(
        self,
        media_file_id: str,
        db: AsyncSession,
        analysis_type: str = "compliance",
        check_item_title: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream photo analysis results.
        """
        # Fetch media file
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == media_file_id)
        )
        media_file = result.scalar_one_or_none()

        if not media_file:
            yield {"type": "error", "content": "Media file not found"}
            return

        if media_file.file_type != "image":
            yield {"type": "error", "content": "Only image files can be analyzed"}
            return

        # Read and encode image
        try:
            image_base64 = self._read_and_encode_image(media_file.file_path)
        except Exception as e:
            yield {"type": "error", "content": f"Failed to read image: {str(e)}"}
            return

        # Build prompt
        prompt = PHOTO_ANALYSIS_PROMPT
        if check_item_title:
            prompt = f"检查项：{check_item_title}\n\n{prompt}"

        # Stream analysis
        full_content = ""
        try:
            stream = await self._stream_vision_api(prompt, image_base64)

            async for chunk in stream:
                if chunk:
                    full_content += chunk
                    yield {"type": "thinking", "content": chunk}

            analysis_result = self._parse_analysis_response(full_content)
            yield {
                "type": "done",
                "content": analysis_result,
                "full_content": full_content
            }

        except Exception as e:
            print(f"[Multimodal] Stream error: {e}")
            yield {"type": "error", "content": str(e)}

    async def batch_analyze_photos(
        self,
        media_file_ids: List[str],
        db: AsyncSession,
        analysis_type: str = "compliance",
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple photos in batch.
        """
        results = []
        for media_id in media_file_ids:
            result = await self.analyze_photo(media_id, db, analysis_type)
            results.append(result)
        return results

    async def get_photo_analysis(
        self,
        media_file_id: str,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing analysis for a photo.
        """
        result = await db.execute(
            select(PhotoAnalysis)
            .where(PhotoAnalysis.media_file_id == media_file_id)
            .order_by(PhotoAnalysis.created_at.desc())
        )
        analysis = result.scalar_one_or_none()

        if not analysis:
            return None

        return {
            "id": str(analysis.id),
            "media_file_id": str(analysis.media_file_id),
            "analysis_type": analysis.analysis_type,
            "detected_issues": json.loads(analysis.detected_issues) if analysis.detected_issues else [],
            "compliance_status": analysis.compliance_status,
            "confidence_score": analysis.confidence_score,
            "analysis_result": analysis.analysis_result,
            "recommendations": json.loads(analysis.recommendations) if analysis.recommendations else [],
            "model_used": analysis.model_used,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }

    def _read_and_encode_image(self, file_path: str) -> str:
        """Read image file and encode to base64."""
        import os

        # Normalize the path - remove leading slash if present and handle relative paths
        # File path might be stored as "/uploads/..." or "uploads/..."
        if file_path.startswith("/"):
            file_path = file_path[1:]  # Remove leading slash

        # If path starts with "uploads/", make it relative to UPLOAD_DIR's parent
        if file_path.startswith("uploads/"):
            # Get the base directory (parent of uploads)
            base_dir = os.path.dirname(settings.UPLOAD_DIR.rstrip("/\\"))
            if not base_dir:
                base_dir = "."
            file_path = os.path.join(base_dir, file_path)
        elif not os.path.isabs(file_path):
            # Other relative paths - join with UPLOAD_DIR
            file_path = os.path.join(settings.UPLOAD_DIR, file_path)

        # Debug logging
        print(f"[Multimodal] Reading image from: {file_path}")

        with open(file_path, "rb") as f:
            image_data = f.read()

        return base64.b64encode(image_data).decode("utf-8")

    async def _call_vision_api(
        self,
        prompt: str,
        image_base64: str,
    ) -> str:
        """Call vision-capable LLM API using OpenAI-style image format."""
        response = await self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "auto"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content or ""

    async def _stream_vision_api(
        self,
        prompt: str,
        image_base64: str,
    ) -> AsyncGenerator[str, None]:
        """Stream from vision-capable LLM API."""
        stream = await self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "auto"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured analysis result."""
        result = {
            "description": "",
            "issues": [],
            "compliance_status": "unknown",
            "confidence": 0.5,
            "recommendations": [],
        }

        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                result.update(parsed)
                return result
            except json.JSONDecodeError:
                pass

        # Fallback: use response as description
        result["description"] = response

        # Try to detect compliance status from text
        response_lower = response.lower()
        if any(kw in response_lower for kw in ["不合规", "non_compliant", "问题", "缺陷", "不合格"]):
            result["compliance_status"] = "non_compliant"
        elif any(kw in response_lower for kw in ["合规", "compliant", "符合", "合格"]):
            result["compliance_status"] = "compliant"
        elif any(kw in response_lower for kw in ["警告", "warning", "注意", "需改进"]):
            result["compliance_status"] = "warning"

        return result


multimodal_service = MultimodalService()