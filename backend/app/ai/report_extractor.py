import re
import logging
from datetime import date, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)


class ExecutionReportExtraction(BaseModel):
    intent: str = Field(description="PROJECT_QUERY or EXECUTION_REPORT")
    activity_description: Optional[str] = Field(default=None, description="Extracted natural language activity description, e.g. 'Foundation concreting'")
    explicit_activity_code: Optional[str] = Field(default=None, description="Explicit activity code if present in text, e.g. 'CIV-103'")
    update_type: Optional[str] = Field(default="PROGRESS", description="START, PROGRESS, COMPLETE, ON_HOLD, or RESUME")
    progress_percentage: Optional[float] = Field(default=None, description="Progress percentage 0 to 100 if specified")
    reported_date: Optional[str] = Field(default=None, description="Date string YYYY-MM-DD")
    remarks: Optional[str] = Field(default=None, description="Optional remarks or reason, e.g. 'material has not arrived'")
    clarification_question: Optional[str] = Field(default=None, description="Question to ask user if vital info like progress percentage is missing")


# Reporting keywords & patterns
REPORTING_VERB_PATTERNS = [
    r"\b(started|began|commenced)\b",
    r"\b(reached|progressed to|progress is|at)\s+\d+\s*(%|percent)\b",
    r"\b\d+\s*(%|percent)\s*(complete|completed|done|progress)?\b",
    r"\b(completed|finished|done)\b",
    r"\b(put on hold|on hold|paused|stopped)\b",
    r"\b(resume|resumed|restarted|continued)\b",
]

QUESTION_PATTERNS = [
    r"^\s*(what|how|who|when|where|why|is|are|can|could|would|show|list|get)\b",
    r"\?\s*$",
]


def classify_intent_deterministic(prompt: str) -> str:
    """Classifies prompt as PROJECT_QUERY or EXECUTION_REPORT deterministically."""
    lowered = prompt.strip().lower()

    # If it ends with question mark or starts with interrogative word, high chance of query
    is_question = any(re.search(pat, lowered) for pat in QUESTION_PATTERNS)
    if is_question and not re.search(r"\b(is|now)\s+\d+%\s*(complete|done)\b", lowered):
        return "PROJECT_QUERY"

    # Check for reporting verbs/patterns
    has_reporting_verb = any(re.search(pat, lowered) for pat in REPORTING_VERB_PATTERNS)
    if has_reporting_verb:
        return "EXECUTION_REPORT"

    # Check for explicit code + reporting status
    if re.search(r"\b[A-Za-z]{2,5}-\d{1,5}\b", prompt) and any(w in lowered for w in ["complete", "started", "done", "progress", "hold", "resume"]):
        return "EXECUTION_REPORT"

    return "PROJECT_QUERY"


def parse_execution_report_fallback(prompt: str) -> ExecutionReportExtraction:
    """Fallback deterministic regex parser for structured execution report extraction."""
    intent = classify_intent_deterministic(prompt)
    if intent == "PROJECT_QUERY":
        return ExecutionReportExtraction(intent="PROJECT_QUERY")

    lowered = prompt.strip().lower()

    # 1. Explicit activity code
    code_match = re.search(r"\b([A-Za-z]{2,5}-\d{1,5})\b", prompt, re.IGNORECASE)
    explicit_code = code_match.group(1).upper() if code_match else None

    # 2. Update type
    update_type = "PROGRESS"
    if re.search(r"\b(put on hold|on hold|paused|stopped)\b", lowered):
        update_type = "ON_HOLD"
    elif re.search(r"\b(resume|resumed|restarted|continued)\b", lowered):
        update_type = "RESUME"
    elif re.search(r"\b(completed|finished|done)\b", lowered):
        update_type = "COMPLETE"
    elif re.search(r"\b(started|began|commenced)\b", lowered):
        update_type = "START"
    elif re.search(r"\b(reached|progress|percent|%)\b", lowered):
        update_type = "PROGRESS"

    # 3. Progress percentage
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", lowered)
    progress_percentage = float(pct_match.group(1)) if pct_match else None

    if update_type == "COMPLETE" and progress_percentage is None:
        progress_percentage = 100.0

    # Missing progress check for PROGRESS update
    clarification_question = None
    if update_type == "PROGRESS" and progress_percentage is None:
        clarification_question = "What percentage is the activity currently complete?"

    # 4. Date extraction
    rep_date = date.today().isoformat()
    if "yesterday" in lowered:
        rep_date = (date.today() - timedelta(days=1)).isoformat()
    else:
        # Check explicit YYYY-MM-DD or DD-MM-YYYY
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", prompt)
        if date_match:
            rep_date = date_match.group(1)

    # 5. Remarks extraction
    remarks = None
    reason_match = re.search(r"\b(?:because|due to|as|reason:)\s+(.+)$", prompt, re.IGNORECASE)
    if reason_match:
        remarks = reason_match.group(1).strip()

    # 6. Activity description extraction
    clean_desc = prompt
    if explicit_code:
        clean_desc = re.sub(re.escape(explicit_code), "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(today|yesterday|this morning)\b", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(we|started|began|commenced|reached|progress|completed|finished|done|put on hold|on hold|paused|stopped|resume|resumed|restarted|continued)\b", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\d+(?:\.\d+)?\s*(?:%|percent)", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(?:because|due to|as)\s+.+$", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"[^\w\s\-]", " ", clean_desc).strip()

    activity_description = clean_desc if clean_desc and len(clean_desc) > 2 else None

    res_data = ExecutionReportExtraction(
        intent="EXECUTION_REPORT",
        activity_description=activity_description,
        explicit_activity_code=explicit_code,
        update_type=update_type,
        progress_percentage=progress_percentage,
        reported_date=rep_date,
        remarks=remarks,
        clarification_question=clarification_question,
    )
    return normalize_execution_extraction(res_data, prompt)


def normalize_execution_extraction(data: ExecutionReportExtraction, prompt: str) -> ExecutionReportExtraction:
    """
    Deterministically normalizes update_type and progress_percentage.
    Explicit partial percentages (1 <= percentage <= 99) override update_type to PROGRESS.
    Percentage == 100 normalizes update_type to COMPLETE and progress_percentage to 100.
    """
    if data.intent != "EXECUTION_REPORT":
        return data

    pct = data.progress_percentage
    if pct is None:
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", prompt, re.IGNORECASE)
        if pct_match:
            try:
                pct = float(pct_match.group(1))
            except ValueError:
                pass

    if pct is not None:
        if 1.0 <= pct <= 99.0:
            data.update_type = "PROGRESS"
            data.progress_percentage = pct
            data.clarification_question = None
        elif pct >= 100.0:
            data.update_type = "COMPLETE"
            data.progress_percentage = 100.0
            data.clarification_question = None

    return data


def extract_execution_report(prompt: str) -> ExecutionReportExtraction:
    """
    Extracts structured execution intent from prompt.
    Uses Gemini API if key is available, falling back to deterministic parser.
    """
    api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""

    data = None
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
            sys_inst = (
                "You are a strict data extraction system for a construction management system. "
                "Classify whether the user message is a PROJECT_QUERY or an EXECUTION_REPORT. "
                "For EXECUTION_REPORT, extract: update_type (START, PROGRESS, COMPLETE, ON_HOLD, RESUME), "
                "progress_percentage (float), reported_date (YYYY-MM-DD using today's date if 'today' or unspecified), "
                "explicit_activity_code if present (e.g. CIV-103), activity_description, and remarks. "
                "IMPORTANT: If an explicit percentage between 1% and 99% is provided (e.g. '20% completed'), update_type MUST be PROGRESS. "
                f"Today's date is {date.today().isoformat()}."
            )

            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExecutionReportExtraction,
                    system_instruction=sys_inst,
                    temperature=0.0,
                ),
            )
            if res.text:
                data = ExecutionReportExtraction.model_validate_json(res.text)
                if not data.reported_date:
                    data.reported_date = date.today().isoformat()
        except Exception as e:
            logger.warning(f"Gemini extraction call failed, using fallback parser: {e}")

    if data is None:
        data = parse_execution_report_fallback(prompt)

    return normalize_execution_extraction(data, prompt)

