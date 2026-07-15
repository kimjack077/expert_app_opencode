from app.services.rag_service import rag_service


def test_section_match_distinguishes_toc_from_clause_body():
    toc = "3.5 追溯系统 ........................................ 2"
    body = "3.5 追溯系统 基于追溯码、文件记录和通信网络，实现信息化管理。"

    assert rag_service._get_section_match_type(toc, {"3.5"}) == "toc"
    assert rag_service._get_section_match_type(body, {"3.5"}) == "body"


def test_section_match_ignores_heading_without_its_body():
    partial_chunk = "3.4 追溯单元的定义。3.5 追溯系统"

    assert rag_service._get_section_match_type(partial_chunk, {"3.5"}) is None


def test_table_of_contents_chunk_is_detected_but_regular_clause_is_not():
    toc = """1 范围 ................................ 1
2 规范性引用文件 ......................... 1
3 术语和定义 ............................. 1
3.5 追溯系统 ............................ 2"""
    clause = "3.5 追溯系统 基于追溯码、文件记录和通信网络，实现信息化管理。"

    assert rag_service._is_table_of_contents_chunk(toc)
    assert not rag_service._is_table_of_contents_chunk(clause)
