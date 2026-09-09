import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from rapidfuzz import fuzz

from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution


def match_activity_for_report(
    db: Session,
    project_id: int,
    user_role: str,
    user_discipline: Optional[str],
    explicit_activity_code: Optional[str] = None,
    activity_description: Optional[str] = None,
    update_type: str = "PROGRESS",
) -> Tuple[Optional[Activity], float, str, List[Dict[str, Any]]]:
    """
    Candidate activity matcher for natural-language execution reporting.
    
    Returns: (matched_activity_obj, match_confidence_score, match_status_enum, alternative_candidates_list)
    
    Rules:
    1. STRICT DISCIPLINE SCOPING:
       - If user is SUPERVISOR, restrict candidate universe ONLY to activities matching user_discipline.
       - UNASSIGNED activities or cross-discipline activities are excluded.
    2. EXACT ACTIVITY CODE MATCH:
       - If explicit_activity_code is provided (e.g. CIV-103), search candidate universe.
       - If found: confidence = 1.0, status = "MATCHED_HIGH".
    3. HYBRID FUZZY MATCHING:
       - Match normalized activity_description against activity_code and activity_name.
       - Calculate combination of token_set_ratio, token_sort_ratio, and partial_ratio.
       - Boost score if execution state is compatible (e.g. START requires NOT_STARTED, COMPLETE requires IN_PROGRESS).
    4. CONFIDENCE THRESHOLDS:
       - HIGH: >= 0.85 -> MATCHED_HIGH
       - MEDIUM: 0.65 - 0.84 -> MATCHED_MEDIUM
       - LOW: < 0.65 -> UNMATCHED
    """
    # 1. Build authorized candidate activity query
    query = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project_id)
    )

    # Supervisor Discipline Restriction
    effective_discipline = None
    if user_role == "SUPERVISOR":
        if not user_discipline:
            return None, 0.0, "UNMATCHED", []
        effective_discipline = user_discipline.strip().upper()
        query = query.filter(func.upper(Activity.discipline) == effective_discipline)

    candidates = query.all()
    if not candidates:
        return None, 0.0, "UNMATCHED", []

    # 2. Check Explicit Activity Code match
    if explicit_activity_code and explicit_activity_code.strip():
        code_clean = explicit_activity_code.strip().upper()
        for act, exec_obj in candidates:
            if act.activity_code.upper() == code_clean:
                return act, 1.0, "MATCHED_HIGH", []

        # Substring/partial match on explicit code
        for act, exec_obj in candidates:
            if code_clean in act.activity_code.upper():
                return act, 0.95, "MATCHED_HIGH", []

    # 3. Description Fuzzy Matching
    if not activity_description or not activity_description.strip():
        return None, 0.0, "UNMATCHED", []

    desc_clean = activity_description.strip().lower()

    scored_list = []

    for act, exec_obj in candidates:
        act_name_lower = (act.activity_name or "").lower()
        act_code_lower = (act.activity_code or "").lower()

        # Compute fuzzy similarity scores
        score_name_token_set = fuzz.token_set_ratio(desc_clean, act_name_lower)
        score_name_token_sort = fuzz.token_sort_ratio(desc_clean, act_name_lower)
        score_code_partial = fuzz.partial_ratio(desc_clean, act_code_lower)

        # Base similarity score (0 to 100)
        base_score = max(
            score_name_token_set,
            score_name_token_sort * 0.9,
            score_code_partial * 0.8
        )

        # Exact substring bonus
        if desc_clean in act_name_lower or act_name_lower in desc_clean:
            base_score = min(100.0, base_score + 15.0)

        # Transition compatibility check
        exec_status = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")

        status_bonus = 0.0
        if update_type == "START" and exec_status == "NOT_STARTED":
            status_bonus = 5.0
        elif update_type in ["PROGRESS", "COMPLETE", "ON_HOLD"] and exec_status == "IN_PROGRESS":
            status_bonus = 5.0
        elif update_type == "RESUME" and exec_status == "ON_HOLD":
            status_bonus = 5.0
        elif update_type == "COMPLETE" and exec_status == "COMPLETED":
            # Penalty for already completed activities
            base_score = base_score * 0.5

        final_score = min(100.0, base_score + status_bonus)
        confidence = round(final_score / 100.0, 2)

        scored_list.append({
            "activity": act,
            "exec_status": exec_status,
            "confidence": confidence,
        })

    # Sort candidates by confidence descending
    scored_list.sort(key=lambda x: x["confidence"], reverse=True)

    if not scored_list:
        return None, 0.0, "UNMATCHED", []

    top_item = scored_list[0]
    top_confidence = top_item["confidence"]
    top_activity = top_item["activity"]

    # Status classification
    if top_confidence >= 0.85:
        match_status = "MATCHED_HIGH"
    elif top_confidence >= 0.65:
        match_status = "MATCHED_MEDIUM"
    else:
        match_status = "UNMATCHED"

    # Build alternative candidate list for UI display
    alternatives = []
    for item in scored_list[:4]:
        act_obj = item["activity"]
        alternatives.append({
            "activity_id": act_obj.id,
            "activity_code": act_obj.activity_code,
            "activity_name": act_obj.activity_name,
            "discipline": act_obj.discipline,
            "confidence": item["confidence"],
            "exec_status": item["exec_status"],
        })

    if match_status == "UNMATCHED":
        return None, top_confidence, "UNMATCHED", alternatives

    return top_activity, top_confidence, match_status, alternatives
