"""Regression cases from the September live-use bug report (synthetic data only)."""
import threading
import time
from zipfile import ZipFile

from yida_ai.adapters.captions.mock import MockCaptionSource
from yida_ai.adapters.captions.translated import TranslatedCaptionSource
from yida_ai.core.models import CaptionEvent, ReplyRequest
from yida_ai.providers.llm.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    _clean_direct_reply,
)
from yida_ai.providers.llm.prompt import build_messages
from yida_ai.retrieval.documents import KnowledgeLibrary, read_document
from yida_ai.retrieval.keyword import KeywordRetriever


def make_docx(path):
    """A real OpenXML Word document: heading, paragraph, and a two-row table."""
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '''<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml"
 ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
        archive.writestr("_rels/.rels", '''<Relationships
 xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Target="word/document.xml"
 Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>
</Relationships>''')
        archive.writestr("word/document.xml", '''<w:document
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>星河服务资料</w:t></w:r></w:p>
<w:p><w:r><w:t>营业时间：周一至周五上午九点到下午六点。</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>项目</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>具体信息</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>维修保修期</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>十二个月</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>''')
    return path


def test_long_translation_is_split_without_losing_text(monkeypatch):
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig("http://localhost/test", "fake", "m")
    )
    seen = []

    def respond(payload):
        text = payload["messages"][-1]["content"]
        seen.append(text)
        assert len(text) <= 1600, "one translation request exceeds the safe output budget"
        return {"translation": text}

    monkeypatch.setattr(provider, "_post_json", respond)
    text = "Uma frase longa com informações importantes. " * 300
    result = provider.translate_text(text, "pt-BR", "zh-CN")
    assert result.replace("\n", "").replace(" ", "") == text.replace(" ", "")
    assert len(seen) > 1


def test_translation_backlog_preserves_independent_sentences():
    gate = threading.Event()

    class Translator:
        def translate_text(self, text, *_):
            gate.wait(3)
            return "translated:" + text

    events = [CaptionEvent(source_text=f"Sentence {n}.", event_id=f"e{n}") for n in range(90)]
    source = TranslatedCaptionSource(MockCaptionSource(events), Translator())
    try:
        first = source.poll(100)
        assert not any(e.metadata.get("translation_error") == "queue-full" for e in first)
        gate.set()
        completed = {}
        deadline = time.monotonic() + 5
        while len(completed) < len(events) and time.monotonic() < deadline:
            for event in source.poll(100):
                if event.translated_text:
                    completed[event.event_id] = event
            time.sleep(.005)
        assert set(completed) == {e.event_id for e in events}
    finally:
        gate.set()
        source.close()


def test_docx_body_and_table_are_imported_and_searchable(tmp_path):
    path = make_docx(tmp_path / "中文 空格服务资料.docx")
    library = KnowledgeLibrary(tmp_path / "knowledge")
    target = library.import_document(path)
    text = read_document(target)
    assert "营业时间" in text and "十二个月" in text and "维修保修期" in text
    retriever = KeywordRetriever()
    retriever.index_directory(library.directory)
    assert "十二个月" in retriever.retrieve("维修保修期是多久")[0].excerpt


def test_prompt_assigns_speaker_and_explicit_latest_question():
    earlier = CaptionEvent(source_text="What do you sell?")
    latest = CaptionEvent(source_text="How long is the warranty?")
    request = ReplyRequest(latest, (earlier,), (), "general", "zh-CN", "en-US", "short", "s")
    messages = build_messages(request)
    assert "first person" in messages[0]["content"].lower()
    assert latest.source_text in messages[-1]["content"]
    assert "you can answer" in messages[0]["content"].lower()


def test_meta_reply_prefix_is_removed_before_display():
    assert _clean_direct_reply("You can answer: We open at nine.") == "We open at nine."
    assert _clean_direct_reply("建议你说：我们周一到周五营业。") == "我们周一到周五营业。"
