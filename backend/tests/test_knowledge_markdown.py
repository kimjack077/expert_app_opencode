import asyncio
import io
import json
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import UploadFile
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from app.models.knowledge import KnowledgeDocument
from app.models.rag import KnowledgeEmbedding
from app.utils.document_parser import document_parser
from app.services.rag_service import rag_service


async def run_all_tests():
    print("========================================")
    print("开始测试知识库 Markdown 解析与流式索引...")
    print("========================================")

    # 1. 测试 TXT / Markdown 解析
    print("\n[Test 1] 测试纯文本/Markdown 解析...")
    sample_text = """# 移动式压力容器充装通用技术要求

## 1 范围
本标准规定了移动式压力容器充装的基本要求、追溯信息管理及人员职责。

## 2 规范性引用文件
- GB/T 19001 质量管理体系 要求
- TSG R0005 移动式压力容器安全技术监察规程

## 3 充装追溯要求
充装单位应建立追溯管理系统，记录充装前检查记录、充装介质种类和数量。
"""
    txt_file = UploadFile(
        filename="test_regulation.txt",
        file=io.BytesIO(sample_text.encode("utf-8")),
    )
    md_out, meta = await document_parser.parse_document(txt_file)
    assert len(md_out) > 0, "解析出的 Markdown 内容不应为空"
    assert meta["filename"] == "test_regulation.txt"
    print(f"[PASS] 文本解析成功，字符数: {len(md_out)}")

    # 2. 测试 Markdown 标题层级切块
    print("\n[Test 2] 测试 Markdown 标题层级切块与面包屑...")
    chunks = rag_service._chunk_markdown(md_out)
    print(f"[PASS] 成功切分为 {len(chunks)} 个片段:")
    for i, c in enumerate(chunks):
        first_line = c.splitlines()[0] if c.splitlines() else ""
        print(f"   Fragment {i+1}: {first_line}")
        assert "[" in first_line and "]" in first_line or len(chunks) == 1, "每个片段应带有面包屑"

    # 3. 数据库与流式 Embedding 索引测试
    print("\n[Test 3] 测试数据库写入与流式创建向量索引...")
    async with AsyncSessionLocal() as db:
        # 创建测试文档
        test_doc = KnowledgeDocument(
            title="自动化测试-移动式压力容器追溯",
            doc_type="standard",
            doc_no="TEST-GB-2026",
            content=md_out,
            keywords="自动化测试,压力容器",
            status="effective",
            file_name="test_regulation.txt",
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)
        doc_id = str(test_doc.id)
        print(f"[PASS] 测试文档已插入数据库，ID: {doc_id}")

        # 运行流式创建向量
        events = []
        async for event in rag_service.create_embeddings_streaming(doc_id, db):
            events.append(event)
            print(f"   [SSE Event] {event}")

        assert any(e.get("stage") == "done" for e in events), "应当包含 done 阶段事件"
        done_event = next(e for e in events if e.get("stage") == "done")
        print(f"[PASS] 流式索引执行完成，生成索引数: {done_event.get('embeddings_created')}")

        # 检查数据库中 embeddings 记录
        emb_res = await db.execute(
            select(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == doc_id)
        )
        embeddings = emb_res.scalars().all()
        assert len(embeddings) > 0, "数据库中应当存在生成的向量切片"
        print(f"[PASS] 数据库中已成功持久化 {len(embeddings)} 条向量切片")

        # 4. 测试基于语义的检索
        print("\n[Test 4] 测试语义向量搜索...")
        search_res = await rag_service.search_knowledge(
            query="充装前检查记录与追溯系统要求",
            db=db,
            top_k=2
        )
        assert len(search_res) > 0, "搜索结果不应为空"
        print(f"[PASS] 成功检索到 {len(search_res)} 条关联知识:")
        for r in search_res:
            print(f"   - 文档: {r['document_title']}, 相似度: {r['similarity']:.3f}")

        # 5. 清理测试数据
        print("\n[Test 5] 清理测试数据...")
        await db.execute(delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == doc_id))
        await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
        await db.commit()
        print("[PASS] 测试数据已清理完毕")

    print("\n========================================")
    print("ALL TESTS PASSED!")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
