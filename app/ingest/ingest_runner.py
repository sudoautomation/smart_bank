# app/ingest/ingest_runner.py — northstar-bank
# Ingestion pipeline: validate → parse → chunk → embed → store.

import json
import pathlib
import uuid
from datetime import datetime, timezone

from psycopg2.extras import execute_values

from config import (
    CHUNK_SIZE, CHUNK_OVERLAP, INGEST_MAX_FILE_MB, INGEST_ALLOWED_TYPES,
    OPENAI_EMBEDDING_MODEL, OPENAI_EMBEDDING_DIMS,
)
from app.utils.db import get_connection
from app.utils.openai_client import get_openai_client
from app.ingest.docling_parser import parse_document


def _embed_batch(texts: list[str]) -> list[list[float]]:
    response = get_openai_client().embeddings.create(
        model=OPENAI_EMBEDDING_MODEL, input=texts, dimensions=OPENAI_EMBEDDING_DIMS,
    )
    return [item.embedding for item in response.data]


def merge_split_tables(elements: list[dict]) -> list[dict]:
    """Merge table chunks split across pages with matching headers."""
    if not elements:
        return elements

    def extract_headers(table_text: str) -> set[str] | None:
        lines = table_text.split("\n")
        if not lines or "|" not in lines[0]:
            return None
        headers = {part.split(":")[0].strip()
                   for part in lines[0].split("|") if ":" in part}
        return headers if headers else None

    def is_header_row(row: str, expected: set[str]) -> bool:
        if "|" not in row:
            return False
        return {part.split(":")[0].strip() for part in row.split("|") if ":" in part} == expected

    non_tables = [element for element in elements if element["content_type"] != "table"]
    table_elements = [element for element in elements if element["content_type"] == "table"]

    groups: dict = {}
    for tbl in table_elements:
        key = (tbl["metadata"]["section"],
               tbl["metadata"]["source_file"])
        groups.setdefault(key, []).append(tbl)

    merged_tables = []
    for group in groups.values():
        if len(group) == 1:
            merged_tables.append(group[0])
            continue

        sorted_group = sorted(group, key=lambda x: x["metadata"]["page_number"] or 0)
        i = 0
        while i < len(sorted_group):
            current = sorted_group[i]
            current_headers = extract_headers(current["content"])
            current_page = current["metadata"]["page_number"] or 0
            merge_group = [current]
            j = i + 1
            while j < len(sorted_group):
                nxt = sorted_group[j]
                nxt_page = nxt["metadata"]["page_number"] or 0
                if (extract_headers(nxt["content"]) == current_headers and nxt_page - current_page <= 2):
                    merge_group.append(nxt)
                    current_page = nxt_page
                    j += 1
                else:
                    break
            if len(merge_group) > 1:
                lines = merge_group[0]["content"].split("\n")
                for tbl in merge_group[1:]:
                    for line in tbl["content"].split("\n"):
                        if current_headers and is_header_row(line.strip(), current_headers):
                            continue
                        if line.strip():
                            lines.append(line)
                merged = merge_group[0].copy()
                merged["content"] = "\n".join(lines)
                merged_tables.append(merged)
            else:
                merged_tables.append(merge_group[0])
            i = j

    result, table_idx = [], 0
    for el in elements:
        if el["content_type"] == "table":
            if table_idx < len(merged_tables):
                result.append(merged_tables[table_idx])
                table_idx += 1
        else:
            result.append(el)
    return result


def chunk_text_elements(elements: list[dict]) -> list[dict]:
    """Split text elements by CHUNK_SIZE with CHUNK_OVERLAP; pass tables/images through."""
    chunked = []
    for el in elements:
        if el["content_type"] == "image":
            chunked.append(el)
            continue

        element_type = el["metadata"]["element_type"]
        if "section_header" in element_type or element_type in ("title", "caption") or el["content_type"] == "table":
            chunked.append(el)
            continue

        text, start = el["content"], 0
        while start < len(text):
            chunk = el.copy()
            chunk["content"] = text[start:start + CHUNK_SIZE]
            chunked.append(chunk)
            if start + CHUNK_SIZE >= len(text):
                break
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunked


def upsert_document(conn, source_file: str, file_path: str) -> str:
    """Insert or update document record; return document_id."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO rag.documents (source_file, file_path, ingested_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (source_file)
            DO UPDATE SET file_path = EXCLUDED.file_path, ingested_at = EXCLUDED.ingested_at
            RETURNING document_id
        """, (source_file, file_path, datetime.now(timezone.utc)))
        row = cur.fetchone()
        conn.commit()
        return str(row[0])


def store_chunks(conn, chunks: list[dict], document_id: str) -> int:
    """Batch-insert chunks into rag.chunks; return row count."""
    if not chunks:
        return 0

    rows = []
    for chunk in chunks:
        meta = chunk["metadata"]
        embedding = chunk["embedding"]
        embedding_str = ("[" + ",".join(str(val)
                         for val in embedding) + "]") if embedding else None
        rows.append((
            str(uuid.uuid4()), document_id,
            chunk["content"], chunk["content_type"], embedding_str,
            meta["source_file"], meta["section"],
            meta["page_number"], meta["element_type"],
            json.dumps(meta["position"]) if meta["position"] else None,
            meta["image_base64"],
        ))

    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO rag.chunks
                (chunk_id, document_id, content, content_type, embedding,
                 source_file, section, page_number, element_type, position, image_base64)
            VALUES %s
        """, rows, template="(%s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s)")
        conn.commit()
    return len(rows)


def run_ingest(file_path: str) -> dict:
    """Run the full ingestion pipeline for a single file."""
    path = pathlib.Path(file_path)

    if not path.exists():
        raise ValueError(f"File not found: {file_path}")
    if path.suffix.lower() not in INGEST_ALLOWED_TYPES:
        raise ValueError(f"Unsupported type: {path.suffix}")
    if path.stat().st_size / (1024 * 1024) > INGEST_MAX_FILE_MB:
        raise ValueError(f"File exceeds {INGEST_MAX_FILE_MB} MB limit.")

    source_file = path.name
    raw_elements = parse_document(file_path)
    merged = merge_split_tables(raw_elements)
    chunks = chunk_text_elements(merged)

    embeddings = _embed_batch([chunk["content"] for chunk in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb

    conn = get_connection()
    try:
        document_id = upsert_document(conn, source_file, file_path)
        stored = store_chunks(conn, chunks, document_id)
    finally:
        conn.close()

    return {
        "document_id":  document_id,
        "source_file":  source_file,
        "total_chunks": stored,
        "text_chunks":  sum(1 for chunk in chunks if chunk["content_type"] == "text"),
        "table_chunks": sum(1 for chunk in chunks if chunk["content_type"] == "table"),
        "image_chunks": sum(1 for chunk in chunks if chunk["content_type"] == "image"),
    }


if __name__ == "__main__":
    print(run_ingest("data/KB_Smart_Banking.pdf"))
