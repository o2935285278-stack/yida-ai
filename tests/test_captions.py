from yida_ai.core.captions import CaptionAssembler, normalize_text


def test_normalize_and_filter_blank(event_factory):
    assembler = CaptionAssembler(settle_seconds=0)
    assert normalize_text("  olá\n  mundo ") == "olá mundo"
    blank = event_factory(text="   ", translated="")
    assert assembler.accept(blank, now=1) == []
    assert assembler.flush(now=2) == []


def test_duplicate_caption_filtered(event_factory):
    assembler = CaptionAssembler(settle_seconds=0, duplicate_window=10)
    first = event_factory("one", "Hello!", "你好！")
    assembler.accept(first, now=1)
    assert assembler.flush(now=2) == [first]
    duplicate = event_factory("two", " Hello! ", "你好！")
    assert assembler.accept(duplicate, now=3) == []
    assert assembler.flush(now=4) == []


def test_split_sentence_and_connector_are_merged(event_factory):
    assembler = CaptionAssembler(settle_seconds=1)
    assembler.accept(event_factory("a", "I chose this product", "我选择这个产品"), now=1)
    assembler.accept(event_factory("b", "because it is fast.", "因为它很快。"), now=1.2)
    merged = assembler.flush(now=3)[0]
    assert merged.source_text == "I chose this product because it is fast."
    assert merged.translated_text == "我选择这个产品 因为它很快。"


def test_progressive_revision_keeps_longest_text(event_factory):
    assembler = CaptionAssembler(settle_seconds=1)
    assembler.accept(event_factory("a", "How", "如何"), now=1)
    assembler.accept(event_factory("b", "How are you?", "你好吗？"), now=1.1)
    finalized = assembler.flush(now=3)[0]
    assert finalized.source_text == "How are you?"
    assert finalized.revision_of == "a"


def test_generated_caption_ids_are_unique():
    from yida_ai.core.models import CaptionEvent

    assert CaptionEvent("one").event_id != CaptionEvent("two").event_id
