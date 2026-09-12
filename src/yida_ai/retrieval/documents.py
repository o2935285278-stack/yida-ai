from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from yida_ai.retrieval.base import DocumentChunk, KnowledgeError

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise KnowledgeError("PDF 支持需要安装可选依赖：pip install 'yida-ai[pdf]'") from exc
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    raise KnowledgeError(f"不支持的资料格式：{suffix or '无扩展名'}")


def split_document(text: str, chunk_size: int = 700, overlap: int = 80) -> list[str]:
    if chunk_size < 100 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("invalid chunk settings")
    normalized = re.sub(r"\r\n?", "\n", text)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n(?=#+\s)", normalized)]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if not paragraph:
            continue
        candidate = f"{buffer}\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
            prefix = buffer[-overlap:] if overlap else ""
            buffer = f"{prefix}\n{paragraph}".strip()
        else:
            buffer = paragraph
        while len(buffer) > chunk_size:
            chunks.append(buffer[:chunk_size])
            buffer = buffer[chunk_size - overlap :]
    if buffer:
        chunks.append(buffer)
    return chunks


def load_chunks(path: Path) -> list[DocumentChunk]:
    text = read_document(path).strip()
    if not text:
        return []
    digest = hashlib.sha256(path.name.encode("utf-8") + text.encode("utf-8")).hexdigest()[:16]
    return [
        DocumentChunk(
            document_id=digest,
            document_name=path.name,
            chunk_id=f"{digest}:{index}",
            text=chunk,
            position=index,
        )
        for index, chunk in enumerate(split_document(text))
    ]


class KnowledgeLibrary:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def import_document(self, source: Path) -> Path:
        source = source.resolve()
        if source.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise KnowledgeError("仅支持 TXT、Markdown 和可复制文本的 PDF")
        target = self.directory / source.name
        if not read_document(source).strip():
            raise KnowledgeError("Empty document / scanned PDF: no extractable text")
        if target.exists() and source != target.resolve():
            if source.read_bytes() == target.read_bytes():
                return target
            index = 2
            while target.exists():
                target = self.directory / f"{source.stem} ({index}){source.suffix}"
                index += 1
        if source != target.resolve():
            shutil.copy2(source, target)
        return target

    def delete_document(self, name: str) -> bool:
        target = (self.directory / Path(name).name).resolve()
        if target.parent != self.directory.resolve():
            raise KnowledgeError("非法资料路径")
        if not target.exists():
            return False
        target.unlink()
        return True

    def list_documents(self) -> tuple[Path, ...]:
        return tuple(
            path
            for path in sorted(self.directory.iterdir())
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )
