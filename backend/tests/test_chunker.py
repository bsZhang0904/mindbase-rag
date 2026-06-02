from app.services.rag.chunker import split_text


def test_split_text_basic():
    text = "段落一内容\n\n段落二内容"
    chunks = split_text(text, chunk_size=100, overlap=10)
    assert len(chunks) >= 1
    assert all(c.text for c in chunks)


def test_split_long_text():
    text = "A" * 1000
    chunks = split_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
