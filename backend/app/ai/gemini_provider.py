import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from google import genai
from google.genai import types

from app.core.config import settings
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


def run_ai_chat_turn(
    db: Session,
    project: Project,
    user: User,
    user_discipline: Optional[str],
    conversation_messages: List[AIMessage],
    user_prompt: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Executes a multi-turn AI chat step.
    Returns (assistant_text, sources_metadata).
    """
    # 1. Check general knowledge scope
    if is_out_of_scope_query(user_prompt):
        return GENERAL_KNOWLEDGE_REFUSAL, []

    # 2. Check read-only write refusal
    if is_write_update_query(user_prompt):
        return NATURAL_LANGUAGE_WRITE_REFUSAL, []

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
) -> Tuple[str, List[Dict[str, Any]]]:
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
            return final_text, executed_sources

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
                "summary": f"Executed tool {tool_name}",
            })

            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"result": tool_res},
                )
            )

        contents.append(types.Content(role="user", parts=function_response_parts))

    return "Response generated with partial tool execution limit.", executed_sources


def _run_fallback_tool_engine(
    db: Session,
    project: Project,
    user: User,
    user_discipline: Optional[str],
    user_prompt: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Deterministic fallback tool engine that inspects prompt intent,
    executes project database tools, and formats structured Markdown response.
    """
    prompt_lower = user_prompt.lower()
    sources: List[Dict[str, Any]] = []

    # Specific activity code search in prompt (e.g. ACT-CIV-001, CIV-103)
    act_match = re.search(r"\b(ACT-[A-Za-z0-9_\-]+|[A-Za-z]{2,5}-\d{1,5})\b", user_prompt, re.IGNORECASE)

    if act_match:
        code = act_match.group(1).upper()
        res = execute_tool(db, project.id, user.role, user_discipline, "get_activity_details", {"activity_code": code})
        if "error" not in res:
            sources.append({"tool": "get_activity_details", "args": {"activity_code": code}})
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
            return text, sources

    # Overview / project completion query
    if any(k in prompt_lower for k in ["overview", "project info", "how much of the project is complete", "status of project", "how is project"]):
        ov = execute_tool(db, project.id, user.role, user_discipline, "get_project_overview", {})
        ex = execute_tool(db, project.id, user.role, user_discipline, "get_execution_summary", {})
        sources.append({"tool": "get_project_overview", "args": {}})
        sources.append({"tool": "get_execution_summary", "args": {}})

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
        return text, sources

    # Today's work query
    if any(k in prompt_lower for k in ["today", "scheduled today", "my work", "what should i work on", "work on today"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_today_work", {})
        sources.append({"tool": "get_today_work", "args": {}})

        scope_str = res.get("scope", "Project-wide")
        acts = res.get("activities", [])

        if not acts:
            return f"There are no active activities scheduled for today ({res['today_date']}) under scope: **{scope_str}**.", sources

        text = f"### Activities Scheduled Today ({res['today_date']}) — {scope_str}\n\n"
        text += f"Found **{len(acts)}** active activity item(s):\n\n"
        for a in acts:
            text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
            text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%** | Due: {a['planned_finish']}\n"
        return text, sources

    # Overdue query
    if any(k in prompt_lower for k in ["overdue", "delayed", "behind schedule", "late"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_overdue_activities", {})
        sources.append({"tool": "get_overdue_activities", "args": {}})

        scope_str = res.get("scope", "Project-wide")
        acts = res.get("activities", [])

        if not acts:
            return f"Great news! There are currently **0 overdue activities** under scope: **{scope_str}**.", sources

        text = f"### Overdue Activities ({len(acts)}) — {scope_str}\n\n"
        for a in acts:
            text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
            text += f"  - Planned Finish: {a['planned_finish']} (**{a['overdue_days']} days overdue**)\n"
            text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%**\n"
        return text, sources

    # Upcoming deadlines query
    if any(k in prompt_lower for k in ["upcoming", "deadline", "due soon", "this week", "next week", "7 days"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_upcoming_deadlines", {"days": 7})
        sources.append({"tool": "get_upcoming_deadlines", "args": {"days": 7}})

        scope_str = res.get("scope", "Project-wide")
        acts = res.get("activities", [])

        if not acts:
            return f"No activities are due in the next 7 days under scope: **{scope_str}**.", sources

        text = f"### Upcoming Deadlines (Next 7 Days) — {scope_str}\n\n"
        for a in acts:
            text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
            text += f"  - Due Date: **{a['planned_finish']}** ({a['days_until_due']} days remaining)\n"
            text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%**\n"
        return text, sources

    # Discipline progress query
    if any(k in prompt_lower for k in ["discipline", "civil", "piping", "electrical", "instrumentation", "mechanical", "structural"]):
        disc_req = None
        for dname in ["CIVIL", "PIPING", "ELECTRICAL", "INSTRUMENTATION", "MECHANICAL", "STRUCTURAL"]:
            if dname.lower() in prompt_lower:
                disc_req = dname
                break

        res = execute_tool(db, project.id, user.role, user_discipline, "get_discipline_progress", {"discipline": disc_req})
        sources.append({"tool": "get_discipline_progress", "args": {"discipline": disc_req}})

        discs = res.get("disciplines", [])
        if not discs:
            return "No discipline progress records found matching your query.", sources

        text = "### Discipline Progress Breakdown\n\n"
        for d in discs:
            text += f"#### Discipline: `{d['discipline']}`\n"
            text += f"- Total Activities: {d['total_activities']}\n"
            text += f"- Overall Progress: **{d['overall_progress_percentage']}%**\n"
            text += f"- Breakdown: `COMPLETED`: {d['completed']}, `IN_PROGRESS`: {d['in_progress']}, `NOT_STARTED`: {d['not_started']}, `ON_HOLD`: {d['on_hold']}\n"
            text += f"- Overdue Activities: **{d['overdue']}**\n\n"
        return text, sources

    # Recent updates query
    if any(k in prompt_lower for k in ["recent", "updates", "site logs", "happened recently", "site reports"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_recent_progress_updates", {"limit": 10})
        sources.append({"tool": "get_recent_progress_updates", "args": {"limit": 10}})

        upd = res.get("updates", [])
        if not upd:
            return "No recent site progress updates have been recorded for this project yet.", sources

        text = f"### Recent Site Progress Audit Updates ({res.get('scope')})\n\n"
        for u in upd:
            text += f"- `{u['activity_code']}` ({u['activity_name']}) — `{u['update_type']}`\n"
            text += f"  - Reported by **{u['reporter_name']}** on {u['reported_date']}\n"
            text += f"  - Progress: **{u['progress_percentage']}%** | Remarks: {u['remarks'] or 'N/A'}\n"
        return text, sources

    # Project team / members / supervisors query
    if any(k in prompt_lower for k in ["supervisor", "supervisors", "team", "who is assigned", "assigned to this project", "project member", "members", "who is the civil supervisor", "team members"]):
        res = execute_tool(db, project.id, user.role, user_discipline, "get_project_team", {})
        sources.append({"tool": "get_project_team", "args": {}})

        scount = res.get("supervisor_count", 0)
        members = res.get("members", [])

        text = f"### Project Team Overview (`{res.get('project_code', '')}`)\n\n"
        text += f"- **Assigned Supervisors**: **{scount}**\n"
        text += f"- **Total Members**: **{res.get('total_members', len(members))}**\n\n"
        text += "#### Team Members & Roles:\n"
        for m in members:
            text += f"- **{m['full_name']}** — `{m['role']}` (Discipline: `{m['discipline']}`)\n"
        return text, sources

    # General activity search fallback
    res = execute_tool(db, project.id, user.role, user_discipline, "search_activities", {"query": user_prompt})
    sources.append({"tool": "search_activities", "args": {"query": user_prompt}})

    acts = res.get("activities", [])
    if not acts:
        ov = execute_tool(db, project.id, user.role, user_discipline, "get_project_overview", {})
        return f"No matching activities found for '{user_prompt}' in project `{ov['project_code']}`.", sources

    text = f"### Search Results for '{user_prompt}' ({len(acts)} matching activity/activities)\n\n"
    for a in acts:
        text += f"- `{a['activity_code']}` — **{a['activity_name']}** (`{a['discipline']}`)\n"
        text += f"  - Baseline: {a['planned_start']} to {a['planned_finish']}\n"
        text += f"  - Status: `{a['status']}` | Progress: **{a['progress_percentage']}%**\n"
    return text, sources
