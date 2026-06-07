# app/ingest/docling_parser.py — northstar-bank
# Parses a PDF with Docling into typed chunks (text, table, image).

import base64
import io
import os
import re

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice, AcceleratorOptions, PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_VLM_MODEL


def _get_vlm() -> ChatOpenAI:
    return ChatOpenAI(model=OPENAI_VLM_MODEL, temperature=0.0, api_key=OPENAI_API_KEY)

_TABLE_LABEL = "table"
_TABLE_NOISE = {"table_of_contents", "table_title", "table_caption"}


def _build_pipeline() -> DocumentConverter:
    opts = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        generate_picture_images=True,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)},
    )


def _get_provenance(node) -> tuple[int | None, dict | None]:
    prov = getattr(node, "prov", None)
    if not prov:
        return None, None
    page_no = prov[0].page_no
    position = None
    if hasattr(prov[0], "bbox") and prov[0].bbox is not None:
        b = prov[0].bbox
        position = {"l": b.l, "t": b.t, "r": b.r, "b": b.b}
    return page_no, position


def _make_metadata(content_type, element_type, current_section, page_no, position, source_file, img_b64=None):
    return {
        "content_type": content_type,
        "element_type": element_type,
        "section": current_section,
        "page_number": page_no,
        "source_file": source_file,
        "position": position,
        "image_base64": img_b64,
    }


def _clean_cell(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
        v = v[1:-1].strip()
    return v


def _extract_table_text(node, doc) -> str:
    """Convert a Docling table node to 'Col: val | Col: val' rows."""
    table_text = ""
    if hasattr(node, "export_to_dataframe"):
        try:
            df = node.export_to_dataframe()
            if df is not None and not df.empty:
                headers = [_clean_cell(str(col)) for col in df.columns]
                rows = []
                for _, row in df.iterrows():
                    pairs = [f"{header}: {_clean_cell(str(cell_val))}" for header, cell_val in zip(headers, row)
                             if _clean_cell(str(cell_val)) not in ("", "nan", "None")]
                    if pairs:
                        rows.append("  |  ".join(pairs))
                table_text = "\n".join(rows)
        except Exception:
            pass
    if not table_text and hasattr(node, "export_to_html"):
        try:
            raw_html = node.export_to_html(doc)
            table_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw_html or "")).strip()
        except Exception:
            pass
    return table_text.strip() or getattr(node, "text", "")


def _extract_image_base64(node, doc) -> str | None:
    try:
        if hasattr(node, "get_image"):
            pil_img = node.get_image(doc)
            if pil_img:
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()
        if hasattr(node, "image") and node.image:
            pil_img = getattr(node.image, "pil_image", None)
            if pil_img:
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return None


def _describe_image(img_b64: str, page_no, source_file: str, caption: str) -> str:
    """Send image to VLM and return a text description."""
    try:
        response = _get_vlm().invoke([HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}},
            {"type": "text", "text": f"Describe this BFSI image. Page {page_no}, file {source_file}. {('Caption: ' + caption) if caption else ''}"},
        ])])
        return response.content.strip()
    except Exception:
        return caption.strip() if caption else f"[Image on page {page_no}]"


def _extract_table_headers(table_text: str) -> set[str] | None:
    if not table_text:
        return None
    first_line = table_text.split("\n")[0]
    if "|" not in first_line:
        return None
    headers = {p.split(":")[0].strip() for p in first_line.split("|") if ":" in p}
    return headers if headers else None


def _is_table_footer(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if t[0] in ("*", "†", "‡", "#", "§", "^", "1", "2", "3"):
        return True
    return bool(re.match(r"^(note|notes|source|sources)\b", t, re.IGNORECASE))


def _last_table_index(chunks: list[dict]) -> int | None:
    for i in range(len(chunks) - 1, -1, -1):
        if chunks[i]["content_type"] == "table":
            return i
    return None


def parse_document(file_path: str) -> list[dict]:
    """Parse a PDF into a flat list of typed chunks: text, table, image."""
    converter = _build_pipeline()
    result = converter.convert(file_path)
    doc = result.document
    source_file = os.path.basename(file_path)

    parsed_chunks: list[dict] = []
    current_section: str | None = None
    last_table_state: dict = {"section": None, "header_row": ""}

    for item in doc.iterate_items():
        node = item[0] if isinstance(item, tuple) else item
        label = str(getattr(node, "label", "")).lower()
        page_no, position = _get_provenance(node)

        if label in ("page_header", "page_footer"):
            continue

        meta_kwargs = dict(current_section=current_section, page_no=page_no,
                           position=position, source_file=source_file)

        if "section_header" in label or label == "title":
            text = getattr(node, "text", "").strip()
            if text:
                current_section = text
                last_table_state = {"section": None, "header_row": ""}
                parsed_chunks.append({
                    "content": text, "content_type": "text",
                    "metadata": _make_metadata("text", label, **meta_kwargs),
                })

        elif label == _TABLE_LABEL:
            table_text = _extract_table_text(node, doc)
            if table_text:
                if _extract_table_headers(table_text) is not None:
                    last_table_state = {"section": current_section, "header_row": table_text.split("\n")[0]}
                elif last_table_state["header_row"] and last_table_state["section"] == current_section:
                    table_text = last_table_state["header_row"] + "\n" + table_text
                parsed_chunks.append({
                    "content": table_text, "content_type": "table",
                    "metadata": _make_metadata("table", "table", **meta_kwargs),
                })

        elif "picture" in label or "figure" in label or label == "chart":
            caption = getattr(node, "text", "") or ""
            img_b64 = _extract_image_base64(node, doc)
            description = _describe_image(img_b64, page_no, source_file, caption) if img_b64 \
                else (caption.strip() or f"[Image on page {page_no}]")
            parsed_chunks.append({
                "content": description, "content_type": "image",
                "metadata": _make_metadata("image", "picture", **meta_kwargs, img_b64=img_b64),
            })

        elif label == "footnote":
            text = getattr(node, "text", "")
            if text and text.strip():
                tbl_idx = _last_table_index(parsed_chunks)
                if tbl_idx is not None and _is_table_footer(text.strip()):
                    parsed_chunks[tbl_idx]["content"] += "\n\n" + text.strip()
                else:
                    parsed_chunks.append({
                        "content": text.strip(), "content_type": "text",
                        "metadata": _make_metadata("text", label, **meta_kwargs),
                    })

        else:
            text = getattr(node, "text", "")
            if text and text.strip():
                parsed_chunks.append({
                    "content": text.strip(), "content_type": "text",
                    "metadata": _make_metadata("text", label, **meta_kwargs),
                })

    return parsed_chunks
