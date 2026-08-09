from yida_ai.core.models import EvidenceStatus, ReplyRequest
from yida_ai.providers.llm.mock import MockLLMProvider
from yida_ai.retrieval.documents import KnowledgeLibrary, split_document
from yida_ai.retrieval.keyword import KeywordRetriever


def test_document_chunking_is_bounded_and_overlapped():
    text = "A" * 130 + "\n\n" + "B" * 130
    chunks = split_document(text, chunk_size=140, overlap=20)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 140 for chunk in chunks)
    assert chunks[1].startswith("A" * 20)


def test_retrieval_ranking_and_source_trace(tmp_path):
    directory = tmp_path / "knowledge"
    directory.mkdir()
    (directory / "alpha.md").write_text("退款政策允许七天内申请退款。", encoding="utf-8")
    (directory / "beta.txt").write_text("技术支持提供网络连接排查。", encoding="utf-8")
    retriever = KeywordRetriever()
    assert retriever.index_directory(directory) == 2
    hits = retriever.retrieve("七天退款政策", limit=2)
    assert hits[0].document_name == "alpha.md"
    assert hits[0].chunk_id
    assert hits[0].score > 0


def test_mock_provider_does_not_invent_without_sources(event_factory):
    event = event_factory(text="What was our revenue?", translated="我们的营收是多少？")
    request = ReplyRequest(event, (event,), (), "business", "zh-CN", "en-US", "short", "s1")
    result = MockLLMProvider().generate(request)
    assert result.evidence_status is EvidenceStatus.NOT_FOUND
    assert "没有明确答案" in result.suggested_reply


def test_library_import_and_delete(tmp_path):
    source = tmp_path / "fictional.txt"
    source.write_text("完全虚构的资料", encoding="utf-8")
    library = KnowledgeLibrary(tmp_path / "library")
    target = library.import_document(source)
    assert target.exists()
    assert library.delete_document(target.name)
    assert not target.exists()
