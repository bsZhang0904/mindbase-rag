"""按段落优先的固定大小切块。"""

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    chunk_index: int
    page_number: int | None = None


def _merge_small_parts(parts: list[str], chunk_size: int) -> list[str]:
    merged: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) + 2 <= chunk_size:
            current = f"{current}\n\n{part}".strip() if current else part
        else:
            if current:
                merged.append(current)
            if len(part) <= chunk_size:
                current = part
            else:
                for i in range(0, len(part), chunk_size):
                    merged.append(part[i : i + chunk_size])
                current = ""
    if current:
        merged.append(current)
    return merged


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[Chunk]:
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    parts = _merge_small_parts(paragraphs, chunk_size)
    chunks: list[Chunk] = []
    index = 0

    for part in parts:
        if len(part) <= chunk_size:
            chunks.append(Chunk(text=part, chunk_index=index))
            index += 1
            continue

        start = 0
        while start < len(part):
            end = min(start + chunk_size, len(part))
            chunks.append(Chunk(text=part[start:end], chunk_index=index))
            index += 1
            if end >= len(part):
                break
            start = max(end - overlap, start + 1)

    return chunks
