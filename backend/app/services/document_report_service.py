import io
import json
import os
import re
import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Tuple, Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session
import pypdf
from PIL import Image
from google import genai
from google.genai import types

from app.core.config import settings
from app.models.user import User
from app.models.project import Project
from app.models.activity import Activity
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem
from app.schemas.progress_report import (
    ProgressReportItemResponse,
    ProgressReportImportResponse,
)
from app.services.activity_matching_service import match_activity_for_report
from app.services.batch_report_service import (
    parse_execution_intent,
    parse_date_value,
    extract_items_from_text_dpr,
    validate_item_execution_transition,
    build_report_item_response,
    build_report_import_response,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 20
SUPPORTED_DOCUMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def validate_and_inspect_document(content: bytes, filename: str) -> Dict[str, Any]:
    """
    Validates file extension, size, and integrity.
    Returns metadata dict: { file_type, ext, page_count, reader, mime_type }
    """
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of 10 MB ({len(content) / (1024 * 1024):.2f} MB upload).",
        )

    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported document format '.{ext}'. Supported document formats are .pdf, .jpg, .jpeg, and .png.",
        )

    if ext == "pdf":
        try:
            file_stream = io.BytesIO(content)
            reader = pypdf.PdfReader(file_stream)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid PDF document: {str(e)}",
            )

        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encrypted or password-protected PDF files cannot be processed. Please upload an unencrypted document.",
            )

        page_count = len(reader.pages)
        if page_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF document contains 0 pages.",
            )

        if page_count > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF exceeds maximum supported limit of {MAX_PDF_PAGES} pages ({page_count} pages detected).",
            )

        return {
            "file_type": "PDF",
            "ext": ext,
            "page_count": page_count,
            "reader": reader,
            "mime_type": "application/pdf",
        }

    else:
        # Image verification
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted image file: {str(e)}",
            )

        mime = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
        return {
            "file_type": "IMAGE",
            "ext": ext,
            "page_count": 1,
            "reader": None,
            "mime_type": mime,
        }


def extract_native_pdf_text(reader: pypdf.PdfReader) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Extracts text page-by-page natively using pypdf.
    Returns: (list_of_pages, is_meaningful_text)
    """
    pages_data: List[Dict[str, Any]] = []
    combined_text = ""

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text_clean = text.strip()
        pages_data.append({"page_num": page_num, "text": text_clean})
        combined_text += " " + text_clean

    combined_clean = combined_text.strip()
    # Check text quality: must have at least 25 characters and alphanumeric words
    has_words = bool(re.search(r"[A-Za-z0-9]{2,}", combined_clean))
    is_meaningful = len(combined_clean) >= 25 and has_words

    return pages_data, is_meaningful


def extract_updates_via_gemini_multimodal(
    content: bytes, mime_type: str, filename: str
) -> List[Dict[str, Any]]:
    """
    Extracts structured site updates from an image or scanned document using Gemini 2.5 Flash multimodal API.
    Logs safe diagnostic information without leaking secrets.
    """
    model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"

    logger.info(f"[Document] filename: {filename}")
    logger.info(f"[Document] MIME type: {mime_type}")
    logger.info(f"[Document] byte size: {len(content)}")
    logger.info(f"[Document] extraction path = IMAGE_MULTIMODAL")
    logger.info(f"[Document] Gemini model: {model_name}")

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    api_key = (settings.GEMINI_API_KEY or "").strip() or os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.error("[Document] Gemini API key not configured; cannot perform multimodal document extraction.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not extract this document. Gemini API key is not configured on the server.",
        )

    try:
        client = genai.Client(api_key=api_key)

        file_part = types.Part.from_bytes(data=content, mime_type=mime_type)

        prompt = """
You are an expert infrastructure project engineer parsing a daily site progress report (DPR) / photo report / scanned sheet.
Read all visible text and captions carefully, and extract EVERY distinct field execution progress update reported for project activities.

Return ONLY a valid JSON array of objects with the following schema:
[
  {
    "activity_code_hint": "CIV-101",
    "description": "Pump House Excavation",
    "discipline_hint": "CIVIL",
    "reported_date": "2026-09-10",
    "update_type": "COMPLETE",
    "progress_percentage": 100,
    "remarks": null,
    "source_page": null,
    "raw_text": "CIV-101 Pump House Excavation completed today."
  }
]

Strict Rules:
- Explicitly read visible printed or handwritten text in the document.
- Extract EVERY distinct execution update.
- Do NOT match against database here.
- Do NOT invent missing values or hallucinate fake progress.
- Partial percentage 1–99 = update_type="PROGRESS", progress_percentage=number (e.g. 60, 40).
- 100% / fully completed = update_type="COMPLETE", progress_percentage=100.
- "started" / commenced = update_type="START", progress_percentage=null.
- "on hold" / paused = update_type="ON_HOLD", progress_percentage=null.
- "resumed" / restarted = update_type="RESUME".
- Preserve exact activity-code hints when visible (e.g. 'CIV-101', 'CIV-102', 'CIV-103', 'PIP-201', 'ELE-301').
- If the document contains no progress updates, return an empty array: [].
- Output ONLY the JSON array without markdown fences or additional prose.
"""

        response = client.models.generate_content(
            model=model_name,
            contents=[file_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )

        has_resp = bool(response and response.text)
        logger.info(f"[Document] Gemini response received = {'yes' if has_resp else 'no'}")
        raw_text = (response.text or "").strip() if response else ""
        logger.info(f"[Document] raw response text length: {len(raw_text)}")

        if not raw_text:
            logger.warning("[Document] Gemini returned empty response text.")
            return []

        # Extract JSON array robustly
        json_match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
        if json_match:
            parsed_json_str = json_match.group(0)
        else:
            parsed_json_str = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
            parsed_json_str = re.sub(r"```\s*$", "", parsed_json_str)

        try:
            parsed = json.loads(parsed_json_str)
        except Exception as json_err:
            logger.error(f"[Document] Failed to parse Gemini response as JSON: {json_err}. Raw text: {raw_text[:300]}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not extract this document. Invalid response format from extraction model.",
            )

        if not isinstance(parsed, list):
            if isinstance(parsed, dict) and "items" in parsed:
                parsed = parsed["items"]
            elif isinstance(parsed, dict) and "updates" in parsed:
                parsed = parsed["updates"]
            else:
                parsed = [parsed] if isinstance(parsed, dict) else []

        valid_items = []
        for item in parsed:
            desc = str(item.get("description") or item.get("raw_description") or "").strip()
            code_hint = item.get("activity_code_hint") or item.get("activity_code") or item.get("code")
            disc_hint = item.get("discipline_hint") or item.get("discipline")

            if not desc and code_hint:
                desc = str(code_hint).strip()
            if not desc:
                continue

            raw_type = item.get("update_type") or item.get("extracted_update_type")
            raw_prog = item.get("progress_percentage") or item.get("extracted_progress_percentage")

            up_type, pct_val = parse_execution_intent(raw_type, raw_prog)

            # Intent refinement according to rules
            type_str = str(raw_type or "").strip().upper()
            if type_str == "COMPLETE" or (pct_val is not None and pct_val == 100.0):
                up_type = "COMPLETE"
                pct_val = 100.0
            elif type_str == "START":
                up_type = "START"
                pct_val = None
            elif type_str == "ON_HOLD":
                up_type = "ON_HOLD"
                pct_val = None
            elif type_str == "RESUME":
                up_type = "RESUME"

            rep_d = item.get("reported_date")

            valid_items.append({
                "raw_description": desc,
                "activity_code_hint": str(code_hint).strip() if code_hint else None,
                "discipline_hint": str(disc_hint).strip().upper() if disc_hint else None,
                "extracted_update_type": up_type,
                "extracted_progress_percentage": pct_val,
                "reported_date": rep_d,
                "remarks": str(item.get("remarks") or "").strip() or None if item.get("remarks") else None,
                "source_page": item.get("source_page"),
                "raw_text": str(item.get("raw_text") or desc).strip(),
            })

        logger.info(f"[Document] parsed item count: {len(valid_items)}")
        return valid_items

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Document] Gemini multimodal document extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not extract this document. Please try again. ({str(e)})",
        )


def deduplicate_extracted_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicates exact duplicate work updates within the same import session."""
    seen = set()
    deduped = []
    for it in items:
        page_val = it.get("source_page") or 0
        desc_norm = re.sub(r"\s+", " ", str(it.get("raw_description") or "").strip().lower())
        up_type = str(it.get("extracted_update_type") or "PROGRESS")
        pct = it.get("extracted_progress_percentage")
        key = (page_val, desc_norm, up_type, pct)
        if key not in seen:
            seen.add(key)
            deduped.append(it)
    return deduped


async def process_document_progress_report(
    db: Session,
    project: Project,
    user: User,
    user_discipline: Optional[str],
    file: UploadFile,
) -> ProgressReportImport:
    """
    Main entry point for Phase 13 Document & Scanned Progress Report Ingestion:
    1. Validates file format and limits.
    2. Runs Stage 1 native text extraction for PDFs.
    3. Runs Stage 2 Gemini multimodal extraction if PDF lacks text or for images.
    4. Normalizes, deduplicates, and runs schedule activity matching.
    5. Creates ProgressReportImport session in REVIEW state with ProgressReportItem records.
    6. Ensures temporary memory/files are cleaned up.
    """
    filename = file.filename or "uploaded_document"
    content = await file.read()

    # 1. Validate & inspect document
    doc_meta = validate_and_inspect_document(content, filename)
    file_type = doc_meta["file_type"]  # "PDF" or "IMAGE"
    page_count = doc_meta["page_count"]
    mime_type = doc_meta["mime_type"]

    extracted_items: List[Dict[str, Any]] = []
    extraction_method = "PDF_TEXT"

    if file_type == "PDF":
        reader = doc_meta["reader"]
        pages_data, has_meaningful_text = extract_native_pdf_text(reader)

        if has_meaningful_text:
            # Stage 1: Parse native text page-by-page
            extraction_method = "PDF_TEXT"
            for p_info in pages_data:
                p_num = p_info["page_num"]
                p_text = p_info["text"]
                if not p_text:
                    continue

                page_items = extract_items_from_text_dpr(p_text)
                for it in page_items:
                    it["source_page"] = p_num
                    it["raw_text"] = it.get("raw_description")
                    extracted_items.append(it)
        else:
            # Stage 2: Scanned PDF -> Gemini Multimodal
            extraction_method = "GEMINI_MULTIMODAL"
            extracted_items = extract_updates_via_gemini_multimodal(content, mime_type, filename)

    else:
        # IMAGE file -> Stage 2: Gemini Multimodal
        extraction_method = "GEMINI_MULTIMODAL"
        extracted_items = extract_updates_via_gemini_multimodal(content, mime_type, filename)

    # Free large memory buffer immediately
    del content

    # 3. Deduplicate extracted items
    deduped_items = deduplicate_extracted_items(extracted_items)

    if not deduped_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable field progress updates were found in this document. Please verify the document contains clear progress statements or use Paste DPR.",
        )

    # 4. Create ProgressReportImport session
    meta_header = json.dumps({
        "page_count": page_count,
        "extraction_method": extraction_method,
        "filename": filename,
    })

    report_import = ProgressReportImport(
        project_id=project.id,
        uploaded_by_id=user.id,
        source_type=file_type,  # "PDF" or "IMAGE"
        original_filename=filename,
        raw_text=meta_header,
        status="REVIEW",
    )
    db.add(report_import)
    db.commit()
    db.refresh(report_import)

    # 5. Build ProgressReportItem entities with schedule matching
    report_items = []
    today = date.today()

    for item in deduped_items:
        raw_desc = str(item.get("raw_description") or "").strip()
        if not raw_desc:
            continue

        explicit_code = item.get("activity_code_hint")
        up_type = item.get("extracted_update_type") or "PROGRESS"
        pct_val = item.get("extracted_progress_percentage")

        raw_d = item.get("reported_date")
        rep_date = parse_date_value(raw_d) if raw_d else today

        source_page = item.get("source_page")
        raw_snippet = item.get("raw_text") or raw_desc

        # Build composite remarks containing page provenance and notes
        remarks_parts = []
        if source_page:
            remarks_parts.append(f"[Page {source_page}]")
        if item.get("remarks"):
            remarks_parts.append(str(item["remarks"]).strip())
        if raw_snippet and raw_snippet != raw_desc:
            remarks_parts.append(f"Source: \"{raw_snippet}\"")
        composite_remarks = " ".join(remarks_parts) if remarks_parts else None

        # Execute Phase 8 candidate activity matching
        matched_act, confidence, match_status, _ = match_activity_for_report(
            db=db,
            project_id=project.id,
            user_role=user.role,
            user_discipline=user_discipline,
            explicit_activity_code=explicit_code,
            activity_description=raw_desc,
            update_type=up_type,
        )

        item_entity = ProgressReportItem(
            report_id=report_import.id,
            project_id=project.id,
            raw_description=raw_desc,
            reported_date=rep_date,
            extracted_update_type=up_type,
            extracted_progress_percentage=pct_val,
            remarks=composite_remarks,
            matched_activity_id=matched_act.id if matched_act else None,
            match_confidence=confidence,
            match_status=match_status,
            review_status="PENDING",
        )
        report_items.append(item_entity)

    if not report_items:
        db.delete(report_import)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not construct valid work update rows from document content.",
        )

    db.bulk_save_objects(report_items)
    db.commit()
    db.refresh(report_import)

    return report_import
