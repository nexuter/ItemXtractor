"""
Helpers for parsing SEC submission text (.txt) files.
"""

from __future__ import annotations

import base64
import binascii
import mimetypes
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


@dataclass
class SubmissionDocument:
    doc_type: str
    sequence: str
    filename: str
    description: str
    text: str


_DOCUMENT_PATTERN = re.compile(r"<DOCUMENT>(.*?)</DOCUMENT>", re.IGNORECASE | re.DOTALL)
_PERIOD_PATTERN = re.compile(
    r"(?:(CONFORMED|CONFIRMED)[\s_\-]+)?PERIOD[\s_\-]*OF[\s_\-]*REPORT\b\s*[:=]?\s*([12]\d{7})",
    re.IGNORECASE,
)


def parse_submission_documents(submission_text: str) -> List[SubmissionDocument]:
    documents: List[SubmissionDocument] = []
    for block in _DOCUMENT_PATTERN.findall(submission_text or ""):
        documents.append(
            SubmissionDocument(
                doc_type=_extract_tag_value(block, "TYPE"),
                sequence=_extract_tag_value(block, "SEQUENCE"),
                filename=_extract_tag_value(block, "FILENAME"),
                description=_extract_tag_value(block, "DESCRIPTION"),
                text=_extract_text_block(block),
            )
        )
    return documents


def extract_period_of_report(submission_text: str) -> Tuple[Optional[str], Optional[int], Dict[str, str]]:
    tags_found: Dict[str, str] = {}
    match = _PERIOD_PATTERN.search(submission_text or "")
    if not match:
        return None, None, tags_found
    raw = match.group(2)
    prefix = (match.group(1) or "").upper()
    label = "CONFORMED PERIOD OF REPORT" if prefix else "PERIOD OF REPORT"
    tags_found[label] = raw
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}", int(raw[:4]), tags_found


def extract_trading_symbols(text: str) -> List[str]:
    symbols = re.findall(
        r'name="dei:TradingSymbol"[^>]*>\s*([A-Za-z0-9.\-]+)\s*<',
        text or "",
        flags=re.IGNORECASE,
    )
    out: List[str] = []
    seen = set()
    for sym in symbols:
        token = sym.strip().upper()
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def select_primary_html_document(
    documents: List[SubmissionDocument],
    expected_form: Optional[str],
) -> Optional[SubmissionDocument]:
    target_form = (expected_form or "").upper().strip()
    candidates: List[Tuple[int, SubmissionDocument]] = []
    for doc in documents:
        payload = doc.text or ""
        score = 0
        doc_type = (doc.doc_type or "").upper().strip()
        filename = (doc.filename or "").strip()
        filename_l = filename.lower()
        if target_form:
            if doc_type == target_form:
                score += 60
            elif doc_type.startswith(target_form):
                score += 45
            elif target_form in doc_type:
                score += 30
        if (doc.sequence or "").strip() == "1":
            score += 20
        if filename_l.endswith((".htm", ".html")):
            score += 20
        if looks_like_html(payload):
            score += 25
        if score > 0:
            candidates.append((score, doc))
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item[0],
            _safe_int(item[1].sequence),
            len(item[1].text or ""),
        ),
        reverse=True,
    )
    return candidates[0][1]


def looks_like_html(text: str) -> bool:
    head = (text or "")[:4000].lower()
    return any(token in head for token in ("<html", "<!doctype html", "<body", "<div", "<table"))


def build_document_lookup(documents: List[SubmissionDocument]) -> Dict[str, SubmissionDocument]:
    lookup: Dict[str, SubmissionDocument] = {}
    for doc in documents:
        filename = (doc.filename or "").strip()
        if not filename:
            continue
        lookup[_normalize_ref(filename)] = doc
    return lookup


def resolve_image_document(
    src: str,
    document_lookup: Dict[str, SubmissionDocument],
) -> Tuple[Optional[bytes], Optional[str]]:
    if not src:
        return None, None
    data_uri = _decode_data_uri(src)
    if data_uri is not None:
        payload, ext = data_uri
        return payload, ext

    ref = _normalize_ref(src)
    if not ref:
        return None, None
    doc = document_lookup.get(ref)
    if not doc:
        doc = document_lookup.get(PurePosixPath(ref).name.lower())
    if not doc:
        return None, None
    payload = decode_submission_document_bytes(doc)
    if payload is None:
        return None, None
    ext = _infer_extension(doc.filename or ref)
    return payload, ext


def decode_submission_document_bytes(doc: SubmissionDocument) -> Optional[bytes]:
    text = (doc.text or "").strip()
    if not text:
        return None
    if looks_like_html(text):
        return text.encode("utf-8")
    if text.lstrip().startswith("begin "):
        try:
            return _decode_uu_payload(text)
        except Exception:
            pass

    compact = re.sub(r"\s+", "", text)
    if compact and re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
        padded = compact + ("=" * ((4 - len(compact) % 4) % 4))
        try:
            return base64.b64decode(padded, validate=False)
        except (binascii.Error, ValueError):
            pass

    return text.encode("utf-8")


def bare_item_key(item_key: str) -> str:
    if re.match(r"^[IVX]+_[0-9]", item_key or "", flags=re.IGNORECASE):
        return item_key.split("_", 1)[1]
    return item_key


def _extract_tag_value(block: str, tag_name: str) -> str:
    match = re.search(rf"<{tag_name}>([^\n\r<]*)", block, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_text_block(block: str) -> str:
    match = re.search(r"<TEXT>(.*?)</TEXT>", block, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    stripped = re.sub(r"<[^>]+>", " ", block)
    return stripped.strip()


def _normalize_ref(value: str) -> str:
    token = (value or "").strip()
    if not token:
        return ""
    parsed = urlparse(token)
    path = parsed.path if parsed.scheme or parsed.netloc else token
    path = path.split("?", 1)[0].split("#", 1)[0].strip()
    return PurePosixPath(path).name.lower() if path else ""


def _decode_data_uri(src: str) -> Optional[Tuple[bytes, str]]:
    match = re.match(r"data:([^;,]+)?(;base64)?,(.*)$", src, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    mime = (match.group(1) or "application/octet-stream").strip().lower()
    payload = match.group(3)
    ext = mimetypes.guess_extension(mime) or ""
    if match.group(2):
        try:
            return base64.b64decode(payload), ext
        except (binascii.Error, ValueError):
            return None
    return payload.encode("utf-8"), ext


def _infer_extension(filename: str) -> str:
    suffix = PurePosixPath(filename or "").suffix
    if suffix:
        return suffix
    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed:
        return mimetypes.guess_extension(guessed) or ""
    return ""


def _safe_int(value: str) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return -1


def _decode_uu_payload(text: str) -> bytes:
    out = bytearray()
    started = False
    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip("\r\n")
        if not started:
            if line.startswith("begin "):
                started = True
            continue
        if line == "end":
            break
        if not line:
            continue
        out.extend(binascii.a2b_uu(line))
    return bytes(out)
