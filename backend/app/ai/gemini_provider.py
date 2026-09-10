import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.datetime_utils import (
    get_today_date,
    get_yesterday_date,
    get_last_week_range,
    get_last_7_days_range,
)
from app.models.project import Project
from app.models.user import User
from app.models.ai_chat import AIMessage
from app.ai.prompts import build_system_prompt
from app.ai.tools import (
    execute_tool,
    get_project_overview,
    get_execution_summary,
    get_today_work,
    get_overdue_activities,
    get_upcoming_deadlines,
    get_activity_details,
    search_activities,
    get_discipline_progress,
    get_recent_progress_updates,
    get_activity_progress_history,
    get_project_team,
    get_activity_timeline,
    get_project_history,
    get_discipline_history,
    search_project_history,
    get_activity_delay_analysis,
)

logger = logging.getLogger(__name__)

GENERAL_KNOWLEDGE_REFUSAL = "I can only assist with information related to the currently selected infrastructure project."
NATURAL_LANGUAGE_WRITE_REFUSAL = "It looks like you're reporting execution progress. Natural-language execution reporting is not enabled in this AI phase yet. Please use the existing Report Progress workflow."

# Common out-of-scope intent triggers
OUT_OF_SCOPE_TRIGGERS = [
    r"\bcapital of\b",
    r"\bwho is the president\b",
    r"\bprime minister\b",
    r"\bweather in\b",
    r"\bwrite a (python|javascript|java|c\+\+|code) (script|program|function)\b",
    r"\bsolve (this|math)\b",
    r"\bmeaning of life\b",
    r"\bworld cup\b",
    r"\brecipe for\b",
    r"\bpoem\b",
]

# Natural language write/update triggers
WRITE_UPDATE_TRIGGERS = [
    r"\breached \d+%\b",
    r"\bmark .* (complete|completed|done)\b",
    r"\bupdate progress to \d+%\b",
    r"\bset status to\b",
    r"\bchange (start|finish|date)\b",
]


def is_out_of_scope_query(prompt: str) -> bool:
    """Checks if a user query is an obvious general-knowledge request."""
    lowered = prompt.lower()
    for pattern in OUT_OF_SCOPE_TRIGGERS:
        if re.search(pattern, lowered):
            return True
    return False


def is_write_update_query(prompt: str) -> bool:
    """Checks if a user query is attempting to modify execution data via natural language."""
    lowered = prompt.lower()
    for pattern in WRITE_UPDATE_TRIGGERS:
        if re.search(pattern, lowered):
            return True
    return False


def extract_evidence_from_sources(sources_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts normalized evidence citations (E1, E2...) from historical tools results."""
    evidence_list: List[Dict[str, Any]] = []
    seen_keys = set()

    for s in sources_data:
        res = s.get("result") or {}
        # If get_activity_timeline or get_project_history or get_discipline_history or search_project_history
        events_list = res.get("events") or res.get("relevant_events") or []
        for ev in events_list:
            if isinstance(ev, dict):
                act_code = ev.get("activity_code") or "N/A"
                ev_date = ev.get("event_date") or ""
                ev_type = ev.get("update_type") or ev.get("event_type") or "EVENT"
                k = (act_code, ev_date, ev_type)
                if k not in seen_keys:
                    seen_keys.add(k)
                    evidence_list.append({
                        "id": f"E{len(evidence_list) + 1}",
                        "activity_code": act_code,
                        "activity_name": ev.get("activity_name") or "",
                        "date": ev_date,
                        "event_type": ev_type,
                        "source": ev.get("source") or "MANUAL",
                        "summary": ev.get("title") or ev.get("remarks") or f"{ev_type} update for {act_code}",
                        "remarks": ev.get("remarks"),
                    })
    return evidence_list[:10]


def run_ai_chat_turn(
    db: Session,
    project: Project,
    user: User,
    user_discipline: Optional[str],
    conversation_messages: List[AIMessage],
    user_prompt: str,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Executes a multi-turn AI chat step.
    Returns (assistant_text, sources_metadata, evidence_list).
    """
    # 1. Check general knowledge scope
    if is_out_of_scope_query(user_prompt):
        return GENERAL_KNOWLEDGE_REFUSAL, [], []

    # 2. Check read-only write refusal
    if is_write_update_query(user_prompt):
        return NATURAL_LANGUAGE_WRITE_REFUSAL, [], []

    sys_prompt = build_system_prompt(
        project_name=project.name,
        project_code=project.project_code,
        user_name=user.full_name,
        user_email=user.email,
        user_role=user.role,
        user_discipline=user_discipline,
    )

    api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""

    # If GEMINI_API_KEY is available, execute via Gemini SDK
    if api_key:
        try:
            return _run_gemini_sdk_turn(
                api_key=api_key,
                db=db,
                project=project,
                user=user,
                user_discipline=user_discipline,
                sys_prompt=sys_prompt,
                conversation_messages=conversation_messages,
                user_prompt=user_prompt,
            )
        except Exception as e:
            logger.warning(f"Gemini SDK call failed, falling back to deterministic tool engine: {e}")

    # Fallback / Key-less deterministic tool execution engine
    return _run_fallback_tool_engine(
        db=db,
        project=project,
        user=user,
        user_discipline=user_discipline,
        user_prompt=user_prompt,
    )


def _run_gemini_sdk_turn(
    api_key: str,
    db: Session,
    project: Project,
    user: User,
    user_discipline: Optional[str],
    sys_prompt: str,
    conversation_messages: List[AIMessage],
    user_prompt: str,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Runs Gemini API turn using google-genai SDK with automatic function calling loop."""
    client = genai.Client(api_key=api_key)
    model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"

    tool_functions = [
        get_project_overview,
        get_execution_summary,
        get_today_work,
        get_overdue_activities,
        get_upcoming_deadlines,
        get_activity_details,
        search_activities,
        get_discipline_progress,
        get_recent_progress_updates,
        get_activity_progress_history,
        get_project_team,
        get_activity_timeline,
        get_project_history,
        get_discipline_history,
        search_project_history,
        get_activity_delay_analysis,
    ]

    contents = []
    # Include bounded conversation history (last 10 messages)
    for msg in conversation_messages[-10:]:
        role = "user" if msg.role == "USER" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.content)]))

    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]))

    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        tools=tool_functions,
        temperature=0.2,
    )

    executed_sources: List[Dict[str, Any]] = []

    # Function calling loop (max 6 iterations)
    for iteration in range(6):
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)

        if not function_calls:
            final_text = response.text or ""
            evidence = extract_evidence_from_sources(executed_sources)
            return final_text, executed_sources, evidence

        contents.append(response.candidates[0].content)

        function_response_parts = []
        for call in function_calls:
            tool_name = call.name
            tool_args = call.args if call.args else {}

            tool_res = execute_tool(
                db=db,
                project_id=project.id,
                user_role=user.role,
                user_discipline=user_discipline,
                tool_name=tool_name,
                tool_args=dict(tool_args),
            )

            executed_sources.append({
                "tool": tool_name,
                "args": dict(tool_args),
                "result": tool_res,
                "summary": f"Executed tool {tool_name}",
            })

            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"result": tool_res},
                )
            )

        contents.append(types.Content(role="user", parts=function_response_parts))

    evidence = extract_evidence_from_sources(executed_sources)
    return "Response generated with partial tool execution limit.", executed_sources, evidence


def _run_fallback_tool_engine(
    db: Session,
    project: Project,
    user: User,
    user_discipline: Optional[str],
    user_prompt: str,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Deterministic fallback tool engine that inspects prompt intent,
    executes project database tools, and formats structured Markdown response with evidence grounding.
    """
    prompt_lower = user_prompt.lower()
    sources: List[Dict[str, Any]] = []

    # Extract activity code pattern (e.g. PIP-201, CIV-103, ACT-001)
    act_match = re.search(r"\b(ACT-[A-Za-z0-9_\-]+|[A-Za-z]{2,5}-\d{1,5}|[A-Za-z]{2,5}\s+\d{1,5})\b", user_prompt, re.IGNORECASE)
    matched_code = None
    if act_match:
        matched_code = act_match.group(1).strip().replace(" ", "-").upper()

    # 1. Delay analysis intent: "Why was PIP-201 delayed?", "delay in PIP-201", "why is CIV-101 late"
    if matched_code and any(k in prompt_lower for k in ["delay", "delayed", "late", "overdue", "why was", "why is"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_activity_delay_analysis", {"activity_code": matched_code})
        sources.append({"tool": "get_activity_delay_analysis", "args": {"activity_code": matched_code}, "result": res})
        evidence = extract_evidence_from_sources(sources)

        if "error" in res:
            return f"Could not analyze delay for `{matched_code}`: {res['error']}", sources, []

        text = f"### Delay Analysis for `{matched_code}`\n\n"
        text += f"**Status**: `{res['state']}`\n\n"
        text += f"{res['summary']}\n\n"

        if res.get("planned_finish"):
            text += f"- **Planned Finish**: {res['planned_finish']}\n"
        if res.get("actual_finish"):
            text += f"- **Actual Finish**: {res['actual_finish']}\n"
        text += f"- **Current Progress**: {res['current_progress']}%\n"

        if res.get("recorded_notes"):
            text += "\n**Recorded Project Notes:**\n"
            for n in res["recorded_notes"]:
                text += f"- *\"{n}\"*\n"

        return text, sources, evidence

    # 2. Activity timeline / history: "What happened to PIP-201?", "timeline for CIV-103", "history of PIP-201", "what happened before PIP-201 reached 40%"
    if matched_code and any(k in prompt_lower for k in ["what happened", "timeline", "history", "before", "updates for", "all updates"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_activity_timeline", {"activity_code": matched_code})
        sources.append({"tool": "get_activity_timeline", "args": {"activity_code": matched_code}, "result": res})
        evidence = extract_evidence_from_sources(sources)

        if "error" in res:
            return f"Could not load timeline for `{matched_code}`: {res['error']}", sources, []

        act_ctx = res.get("activity", {})
        events = res.get("events", [])

        text = f"### Activity History & Timeline for `{act_ctx.get('activity_code')}` — {act_ctx.get('activity_name')}\n\n"
        text += f"- **Discipline**: `{act_ctx.get('discipline')}` | **Current Status**: `{act_ctx.get('current_status')}` (**{act_ctx.get('current_progress')}%**)\n"
        text += f"- **Baseline Schedule**: {act_ctx.get('planned_start')} to {act_ctx.get('planned_finish')}\n\n"

        if not events:
            text += "No historical execution events have been recorded for this activity yet."
            return text, sources, evidence

        text += f"**Recorded Timeline ({len(events)} events):**\n\n"
        for ev in events:
            rep_name = ev.get("reported_by", {}).get("name", "System") if ev.get("reported_by") else "System"
            src = ev.get("source", "MANUAL")
            text += f"- **{ev.get('event_date')}** — `{ev.get('update_type')}` ({ev.get('title')})\n"
            text += f"  - Reported by **{rep_name}** [{src}]\n"
            if ev.get("remarks"):
                text += f"  - Remarks: *\"{ev['remarks']}\"*\n"

        return text, sources, evidence

    # 3. Specific activity details if matched code present
    if matched_code:
        res = execute_tool(db, project.id, user.role, user_discipline, "get_activity_details", {"activity_code": matched_code})
        if "error" not in res:
            sources.append({"tool": "get_activity_details", "args": {"activity_code": matched_code}, "result": res})
            evidence = extract_evidence_from_sources(sources)
            text = f"### Activity Details for `{res['activity_code']}`\n\n"
            text += f"- **Activity Name**: {res['activity_name']}\n"
            text += f"- **Discipline**: `{res['discipline']}`\n"
            text += f"- **Location**: {res['location']}\n"
            text += f"- **Baseline Dates**: {res['planned_start']} to {res['planned_finish']} ({res['planned_duration']} days)\n"
            text += f"- **Current Status**: `{res['status']}`\n"
            text += f"- **Progress**: **{res['progress_percentage']}%**\n"
            if res.get('actual_start'):
                text += f"- **Actual Start**: {res['actual_start']}\n"
            if res.get('actual_finish'):
                text += f"- **Actual Finish**: {res['actual_finish']}\n"

            if res.get("recent_updates"):
                text += "\n**Recent Audit History:**\n"
                for u in res["recent_updates"]:
                    text += f"- {u['reported_date']} by {u['reported_by']}: `{u['update_type']}` - {u['progress_percentage']}% ({u['remarks'] or 'No remarks'})\n"
            return text, sources, evidence

    # 4. Discipline history queries: "What happened in Civil last week?", "Piping history", "Civil updates"
    found_disc = None
    for dname in ["CIVIL", "PIPING", "ELECTRICAL", "INSTRUMENTATION", "MECHANICAL", "STRUCTURAL", "HSE"]:
        if dname.lower() in prompt_lower:
            found_disc = dname
            break

    if found_disc and any(k in prompt_lower for k in ["last week", "yesterday", "last 7 days", "history", "happened in", "what happened"]):
        d_from, d_to = None, None
        if "last week" in prompt_lower:
            lw_mon, lw_sun = get_last_week_range()
            d_from, d_to = str(lw_mon), str(lw_sun)
            period_str = f"Last Calendar Week ({d_from} to {d_to})"
        elif "yesterday" in prompt_lower:
            yest = str(get_yesterday_date())
            d_from, d_to = yest, yest
            period_str = f"Yesterday ({yest})"
        elif "last 7 days" in prompt_lower:
            l7, today = get_last_7_days_range()
            d_from, d_to = str(l7), str(today)
            period_str = f"Last 7 Days ({d_from} to {d_to})"
        else:
            period_str = "Recent Period"

        res = execute_tool(db, project.id, user.role, user_discipline, "get_discipline_history", {
            "discipline": found_disc,
            "date_from": d_from,
            "date_to": d_to,
        })
        sources.append({"tool": "get_discipline_history", "args": {"discipline": found_disc, "date_from": d_from, "date_to": d_to}, "result": res})
        evidence = extract_evidence_from_sources(sources)

        events = res.get("events", [])
        if not events:
            return f"No historical events recorded for **{found_disc}** during {period_str}.", sources, []

        text = f"### Historical Events in `{found_disc}` — {period_str}\n\n"
        text += f"Found **{len(events)}** recorded event(s):\n\n"
        for ev in events:
            text += f"- **{ev.get('event_date')}** — `{ev.get('activity_code')}`: {ev.get('title')}\n"
            if ev.get("remarks"):
                text += f"  - Remarks: *\"{ev['remarks']}\"*\n"
        return text, sources, evidence

    # 5. General project history / daily reports: "What updates were reported yesterday?", "updates today"
    if any(k in prompt_lower for k in ["yesterday", "reported yesterday", "updates yesterday", "last week"]):
        d_from, d_to = None, None
        if "yesterday" in prompt_lower:
            yest = str(get_yesterday_date())
            d_from, d_to = yest, yest
            period_str = f"Yesterday ({yest})"
        elif "last week" in prompt_lower:
            lw_mon, lw_sun = get_last_week_range()
            d_from, d_to = str(lw_mon), str(lw_sun)
            period_str = f"Last Calendar Week ({d_from} to {d_to})"
        else:
            period_str = "Requested Period"

        res = execute_tool(db, project.id, user.role, user_discipline, "get_project_history", {
            "date_from": d_from,
            "date_to": d_to,
        })
        sources.append({"tool": "get_project_history", "args": {"date_from": d_from, "date_to": d_to}, "result": res})
        evidence = extract_evidence_from_sources(sources)

        events = res.get("events", [])
        if not events:
            return f"No historical progress updates recorded for {period_str}.", sources, []

        text = f"### Historical Project Updates — {period_str}\n\n"
        for ev in events:
            text += f"- **{ev.get('event_date')}** — `{ev.get('activity_code')}`: {ev.get('title')} [{ev.get('source')}]\n"
            if ev.get("remarks"):
                text += f"  - Remarks: *\"{ev['remarks']}\"*\n"
        return text, sources, evidence

    # 6. Overview / project completion query
    if any(k in prompt_lower for k in ["overview", "project info", "how much of the project is complete", "status of project", "how is project"]):
        ov = execute_tool(db, project.id, user.role, user_discipline, "get_project_overview", {})
        ex = execute_tool(db, project.id, user.role, user_discipline, "get_execution_summary", {})
        sources.append({"tool": "get_project_overview", "args": {}, "result": ov})
        sources.append({"tool": "get_execution_summary", "args": {}, "result": ex})

        text = f"### Project Operational Overview: `{ov['project_code']}` - {ov['name']}\n\n"
        text += f"- **Status**: `{ov['status']}` | **Location**: {ov['location'] or 'N/A'}\n"
        text += f"- **Planned Schedule**: {ov['planned_start_date']} to {ov['planned_end_date']}\n"
        text += f"- **Total Activities**: {ov['total_activities']} | **Completed**: {ov['completed_activities']}\n"
        text += f"- **Overall Progress**: **{ov['overall_progress']}%** (activity-weighted physical progress)\n\n"
        text += "#### Execution Status Breakdown:\n"
        sc = ex.get("status_counts", {})
        text += f"- `NOT_STARTED`: {sc.get('NOT_STARTED', 0)}\n"
        text += f"- `IN_PROGRESS`: {sc.get('IN_PROGRESS', 0)}\n"
        text += f"- `ON_HOLD`: {sc.get('ON_HOLD', 0)}\n"
        text += f"- `COMPLETED`: {sc.get('COMPLETED', 0)}\n"
        text += f"- **Overdue Count**: {ex.get('overdue_activities_count', 0)}\n"
        text += f"- **Scheduled Today**: {ex.get('today_work_activities_count', 0)}\n"
        return text, sources, []

    # 7. Today's work query
    if any(k in prompt_lower for k in ["today", "scheduled today", "my work", "what should i work on", "work on today"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_today_work", {})
        sources.append({"tool": "get_today_work", "args": {}, "result": res})

        scope_str = res.get("scope", "Project-wide")
        acts = res.get("activities", [])

        if not acts:
            return f"There are no active activities scheduled for today ({res['today_date']}) under scope: **{scope_str}**.", sources, []

        text = f"### Activities Scheduled Today ({res['today_date']}) — {scope_str}\n\n"
        text += f"Found **{len(acts)}** active activity item(s):\n\n"
        for a in acts:
            text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
            text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%** | Due: {a['planned_finish']}\n"
        return text, sources, []

    # 8. Overdue query
    if any(k in prompt_lower for k in ["overdue", "delayed", "behind schedule", "late"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_overdue_activities", {})
        sources.append({"tool": "get_overdue_activities", "args": {}, "result": res})

        scope_str = res.get("scope", "Project-wide")
        acts = res.get("activities", [])

        if not acts:
            return f"Great news! There are currently **0 overdue activities** under scope: **{scope_str}**.", sources, []

        text = f"### Overdue Activities ({len(acts)}) — {scope_str}\n\n"
        for a in acts:
            text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
            text += f"  - Planned Finish: {a['planned_finish']} (**{a['overdue_days']} days overdue**)\n"
            text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%**\n"
        return text, sources, []

    # 9. Upcoming deadlines query
    if any(k in prompt_lower for k in ["upcoming", "deadline", "due soon", "this week", "next week", "7 days"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_upcoming_deadlines", {"days": 7})
        sources.append({"tool": "get_upcoming_deadlines", "args": {"days": 7}, "result": res})

        scope_str = res.get("scope", "Project-wide")
        acts = res.get("activities", [])

        if not acts:
            return f"No activities are due in the next 7 days under scope: **{scope_str}**.", sources, []

        text = f"### Upcoming Deadlines (Next 7 Days) — {scope_str}\n\n"
        for a in acts:
            text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
            text += f"  - Due Date: **{a['planned_finish']}** ({a['days_until_due']} days remaining)\n"
            text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%**\n"
        return text, sources, []

    # 10. Discipline progress query
    if found_disc or any(k in prompt_lower for k in ["discipline", "disciplines"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_discipline_progress", {"discipline": found_disc})
        sources.append({"tool": "get_discipline_progress", "args": {"discipline": found_disc}, "result": res})

        discs = res.get("disciplines", [])
        if not discs:
            return "No discipline progress records found matching your query.", sources, []

        text = "### Discipline Progress Breakdown\n\n"
        for d in discs:
            text += f"#### Discipline: `{d['discipline']}`\n"
            text += f"- Total Activities: {d['total_activities']}\n"
            text += f"- Overall Progress: **{d['overall_progress_percentage']}%**\n"
            text += f"- Breakdown: `COMPLETED`: {d['completed']}, `IN_PROGRESS`: {d['in_progress']}, `NOT_STARTED`: {d['not_started']}, `ON_HOLD`: {d['on_hold']}\n"
            text += f"- Overdue Activities: **{d['overdue']}**\n\n"
        return text, sources, []

    # 11. Recent updates query
    if any(k in prompt_lower for k in ["recent", "updates", "site logs", "happened recently", "site reports"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_recent_progress_updates", {"limit": 10})
        sources.append({"tool": "get_recent_progress_updates", "args": {"limit": 10}, "result": res})

        upd = res.get("updates", [])
        if not upd:
            return "No recent site progress updates have been recorded for this project yet.", sources, []

        text = f"### Recent Site Progress Audit Updates ({res.get('scope')})\n\n"
        for u in upd:
            text += f"- `{u['activity_code']}` ({u['activity_name']}) — `{u['update_type']}`\n"
            text += f"  - Reported by **{u['reporter_name']}** on {u['reported_date']}\n"
            text += f"  - Progress: **{u['progress_percentage']}%** | Remarks: {u['remarks'] or 'N/A'}\n"
        return text, sources, []

    # 12. Project team / members / supervisors query
    if any(k in prompt_lower for k in ["supervisor", "supervisors", "team", "who is assigned", "assigned to this project", "project member", "members", "who is the civil supervisor", "team members"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_project_team", {})
        sources.append({"tool": "get_project_team", "args": {}, "result": res})

        scount = res.get("supervisor_count", 0)
        members = res.get("members", [])

        text = f"### Project Team Overview (`{res.get('project_code', '')}`)\n\n"
        text += f"- **Assigned Supervisors**: **{scount}**\n"
        text += f"- **Total Members**: **{res.get('total_members', len(members))}**\n\n"
        text += "#### Team Members & Roles:\n"
        for m in members:
            text += f"- **{m['full_name']}** — `{m['role']}` (Discipline: `{m['discipline']}`)\n"
        return text, sources, []

    # 13. Search project history query
    if any(k in prompt_lower for k in ["search", "find update", "look for", "show all updates"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "search_project_history", {"query": user_prompt})
        sources.append({"tool": "search_project_history", "args": {"query": user_prompt}, "result": res})
        evidence = extract_evidence_from_sources(sources)

        events = res.get("events", [])
        if events:
            text = f"### Historical Records Search for *\"{user_prompt}\"*\n\n"
            text += f"Found **{len(events)}** matching historical record(s):\n\n"
            for ev in events:
                text += f"- **{ev.get('event_date')}** — `{ev.get('activity_code')}`: {ev.get('title')}\n"
                if ev.get("remarks"):
                    text += f"  - Remarks: *\"{ev['remarks']}\"*\n"
            return text, sources, evidence

    # 14. General activity search fallback
    res = execute_tool(db, project.id, user.role, user_discipline, "search_activities", {"query": user_prompt})
    sources.append({"tool": "search_activities", "args": {"query": user_prompt}, "result": res})

    acts = res.get("activities", [])
    if not acts:
        ov = execute_tool(db, project.id, user.role, user_discipline, "get_project_overview", {})
        return f"No matching activities found for '{user_prompt}' in project `{ov.get('project_code', '')}`.", sources, []

    text = f"### Search Results for '{user_prompt}' ({len(acts)} matching activity/activities)\n\n"
    for a in acts:
        text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
        text += f"  - Baseline: {a['planned_start']} to {a['planned_finish']}\n"
        text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%**\n"
    return text, sources, []
