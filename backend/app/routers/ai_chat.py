import json
from datetime import datetime, timezone, date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.ai_chat import AIConversation, AIMessage
from app.models.execution_report_draft import ExecutionReportDraft
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.schemas.ai_chat import (
    AIChatRequest,
    AIChatResponse,
    AIConversationListItem,
    AIConversationResponse,
    AIMessageResponse,
    ExecutionReportDraftResponse,
    SelectActivityRequest,
)
from app.schemas.execution import ProgressReportRequest, UpdateTypeEnum
from app.core.dependencies import get_current_user
from app.services.project_service import verify_project_access
from app.services.activity_matching_service import match_activity_for_report
from app.services.execution_service import process_progress_update, verify_supervisor_discipline_authorization
from app.ai.gemini_provider import run_ai_chat_turn
from app.ai.report_extractor import extract_execution_report

router = APIRouter(prefix="/projects", tags=["Project AI Assistant"])


def build_draft_response(db: Session, draft: ExecutionReportDraft) -> ExecutionReportDraftResponse:
    matched_act = draft.matched_activity
    code = matched_act.activity_code if matched_act else None
    name = matched_act.activity_name if matched_act else None
    discipline = matched_act.discipline if matched_act else None

    current_status = None
    current_progress = None
    proposed_status = None
    proposed_progress = None

    if matched_act:
        exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == matched_act.id).first()
        current_status = exec_obj.execution_status if exec_obj else "NOT_STARTED"
        current_progress = exec_obj.progress_percentage if exec_obj else 0.0

        if draft.update_type == "START":
            proposed_status = "IN_PROGRESS"
            proposed_progress = draft.progress_percentage if (draft.progress_percentage is not None and draft.progress_percentage > 0) else current_progress
        elif draft.update_type == "PROGRESS":
            proposed_status = "IN_PROGRESS"
            proposed_progress = draft.progress_percentage if draft.progress_percentage is not None else current_progress
        elif draft.update_type == "COMPLETE":
            proposed_status = "COMPLETED"
            proposed_progress = 100.0
        elif draft.update_type == "ON_HOLD":
            proposed_status = "ON_HOLD"
            proposed_progress = current_progress
        elif draft.update_type == "RESUME":
            proposed_status = "IN_PROGRESS"
            proposed_progress = current_progress

    alternatives = []
    if draft.match_status in ["MATCHED_MEDIUM", "UNMATCHED"]:
        user_disc = discipline
        if not user_disc and draft.reported_by and draft.reported_by.memberships:
            user_disc = draft.reported_by.memberships[0].discipline
        _, _, _, alternatives = match_activity_for_report(
            db=db,
            project_id=draft.project_id,
            user_role="SUPERVISOR",
            user_discipline=user_disc,
            activity_description=draft.original_text,
            update_type=draft.update_type,
        )

    return ExecutionReportDraftResponse(
        id=draft.id,
        project_id=draft.project_id,
        reported_by_id=draft.reported_by_id,
        conversation_id=draft.conversation_id,
        original_text=draft.original_text,
        intent=draft.intent,
        update_type=draft.update_type,
        reported_date=str(draft.reported_date),
        progress_percentage=draft.progress_percentage,
        remarks=draft.remarks,
        matched_activity_id=draft.matched_activity_id,
        matched_activity_code=code,
        matched_activity_name=name,
        matched_discipline=discipline,
        current_status=current_status,
        current_progress=current_progress,
        proposed_status=proposed_status,
        proposed_progress=proposed_progress,
        match_confidence=draft.match_confidence,
        match_status=draft.match_status,
        status=draft.status,
        error_message=draft.error_message,
        alternatives=alternatives,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.post(
    "/{project_id}/ai/chat",
    response_model=AIChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the Project-Specific AI Assistant",
)
def send_ai_chat_message(
    project_id: int,
    req: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sends an operational query or natural language execution progress report to the Project AI.
    - PROJECT_QUERY: Executes read-only project tools.
    - EXECUTION_REPORT: Extracts structured update proposal, checks RBAC & state transitions, creates ExecutionReportDraft.
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)

    # Resolve or create conversation
    if req.conversation_id:
        conversation = (
            db.query(AIConversation)
            .filter(
                AIConversation.id == req.conversation_id,
                AIConversation.project_id == project_id,
                AIConversation.user_id == current_user.id,
            )
            .first()
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation ID {req.conversation_id} not found for this project and user.",
            )
    else:
        title = req.prompt.strip()
        if len(title) > 40:
            title = title[:37] + "..."
        conversation = AIConversation(
            project_id=project_id,
            user_id=current_user.id,
            title=title,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save User message
    user_msg = AIMessage(
        conversation_id=conversation.id,
        role="USER",
        content=req.prompt.strip(),
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Step 1: Check intent via extraction engine
    extraction = extract_execution_report(req.prompt.strip())

    if extraction.intent == "EXECUTION_REPORT":
        # RBAC Check: Only Supervisors can report execution progress
        if current_user.role != "SUPERVISOR":
            refusal_text = "Field execution updates must be reported by an assigned Supervisor."
            assistant_msg = AIMessage(conversation_id=conversation.id, role="ASSISTANT", content=refusal_text)
            db.add(assistant_msg)
            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(assistant_msg)
            return AIChatResponse(
                conversation_id=conversation.id,
                conversation_title=conversation.title,
                user_message=AIMessageResponse.model_validate(user_msg),
                assistant_message=AIMessageResponse.model_validate(assistant_msg),
                sources=[],
                response_type="MESSAGE",
            )

        # Missing Info Clarification check
        if extraction.clarification_question:
            assistant_msg = AIMessage(conversation_id=conversation.id, role="ASSISTANT", content=extraction.clarification_question)
            db.add(assistant_msg)
            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(assistant_msg)
            return AIChatResponse(
                conversation_id=conversation.id,
                conversation_title=conversation.title,
                user_message=AIMessageResponse.model_validate(user_msg),
                assistant_message=AIMessageResponse.model_validate(assistant_msg),
                sources=[],
                response_type="MESSAGE",
            )

        # Match activity candidate
        matched_act, confidence, match_status, alternatives = match_activity_for_report(
            db=db,
            project_id=project_id,
            user_role=current_user.role,
            user_discipline=assigned_discipline,
            explicit_activity_code=extraction.explicit_activity_code,
            activity_description=extraction.activity_description,
            update_type=extraction.update_type or "PROGRESS",
        )

        # State transition validation check on matched activity
        if matched_act:
            exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == matched_act.id).first()
            cur_status = exec_obj.execution_status if exec_obj else "NOT_STARTED"
            cur_prog = exec_obj.progress_percentage if exec_obj else 0.0
            actual_start = exec_obj.actual_start if exec_obj else None

            refusal_msg = None
            if extraction.update_type == "START":
                if cur_status == "COMPLETED":
                    refusal_msg = f"Cannot start activity '{matched_act.activity_code}': Activity is already COMPLETED."
                elif actual_start is not None:
                    refusal_msg = f"Activity '{matched_act.activity_code}' has already been started."
            elif extraction.update_type == "PROGRESS":
                if actual_start is None:
                    refusal_msg = f"Activity '{matched_act.activity_code}' must be started before progress can be reported."
                elif cur_status == "ON_HOLD":
                    refusal_msg = f"Activity '{matched_act.activity_code}' is currently ON_HOLD. You must RESUME the activity before updating progress."
                elif cur_status == "COMPLETED":
                    refusal_msg = f"Activity '{matched_act.activity_code}' is already COMPLETED. No further progress updates permitted."
                elif extraction.progress_percentage is not None and extraction.progress_percentage <= cur_prog:
                    refusal_msg = f"Current recorded progress is already {cur_prog:.0f}%. Progress cannot be reduced through normal Supervisor reporting."
            elif extraction.update_type == "COMPLETE":
                if actual_start is None:
                    refusal_msg = f"Activity '{matched_act.activity_code}' must be started before it can be completed."
                elif cur_status == "COMPLETED":
                    refusal_msg = f"Activity '{matched_act.activity_code}' is already completed."
            elif extraction.update_type == "ON_HOLD":
                if actual_start is None or cur_status != "IN_PROGRESS":
                    refusal_msg = f"Only IN_PROGRESS activities can be put ON_HOLD."
            elif extraction.update_type == "RESUME":
                if cur_status != "ON_HOLD":
                    refusal_msg = f"Only ON_HOLD activities can be resumed."

            if refusal_msg:
                assistant_msg = AIMessage(conversation_id=conversation.id, role="ASSISTANT", content=refusal_msg)
                db.add(assistant_msg)
                conversation.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(assistant_msg)
                return AIChatResponse(
                    conversation_id=conversation.id,
                    conversation_title=conversation.title,
                    user_message=AIMessageResponse.model_validate(user_msg),
                    assistant_message=AIMessageResponse.model_validate(assistant_msg),
                    sources=[],
                    response_type="MESSAGE",
                )

        # Parse reported_date
        rep_date_obj = date.today()
        # Determine normalized progress_percentage for draft creation
        norm_progress = extraction.progress_percentage
        up_type = extraction.update_type or "PROGRESS"
        if up_type == "START":
            if norm_progress is None:
                norm_progress = 0.0
        elif up_type == "COMPLETE":
            norm_progress = 100.0
        elif up_type in ["ON_HOLD", "RESUME"]:
            if matched_act:
                exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == matched_act.id).first()
                norm_progress = exec_obj.progress_percentage if exec_obj else 0.0

        # Create ExecutionReportDraft proposal in DB
        draft = ExecutionReportDraft(
            project_id=project_id,
            reported_by_id=current_user.id,
            conversation_id=conversation.id,
            original_text=req.prompt.strip(),
            intent="EXECUTION_REPORT",
            update_type=up_type,
            reported_date=rep_date_obj,
            progress_percentage=norm_progress,
            remarks=extraction.remarks,
            matched_activity_id=matched_act.id if matched_act else None,
            match_confidence=confidence,
            match_status=match_status,
            status="PENDING",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        # Build card text summary for assistant message log
        card_summary = "I matched a schedule activity for your field report. Please review the proposed update below."

        assistant_msg = AIMessage(
            conversation_id=conversation.id,
            role="ASSISTANT",
            content=card_summary,
            metadata_json=json.dumps({"draft_id": draft.id, "match_status": match_status, "confidence": confidence}),
        )
        db.add(assistant_msg)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_msg)

        draft_resp = build_draft_response(db, draft)

        return AIChatResponse(
            conversation_id=conversation.id,
            conversation_title=conversation.title,
            user_message=AIMessageResponse.model_validate(user_msg),
            assistant_message=AIMessageResponse.model_validate(assistant_msg),
            sources=[],
            response_type="PROGRESS_DRAFT",
            draft=draft_resp,
        )

    # Step 2: Handle PROJECT_QUERY turn
    existing_messages = conversation.messages or []
    assistant_text, sources = run_ai_chat_turn(
        db=db,
        project=project,
        user=current_user,
        user_discipline=assigned_discipline,
        conversation_messages=existing_messages,
        user_prompt=req.prompt.strip(),
    )

    # Save Assistant message
    assistant_msg = AIMessage(
        conversation_id=conversation.id,
        role="ASSISTANT",
        content=assistant_text,
        metadata_json=json.dumps(sources) if sources else None,
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)
    db.refresh(conversation)

    return AIChatResponse(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        user_message=AIMessageResponse.model_validate(user_msg),
        assistant_message=AIMessageResponse.model_validate(assistant_msg),
        sources=sources,
        response_type="MESSAGE",
    )


# Draft Endpoints
@router.post(
    "/{project_id}/ai/progress-drafts/{draft_id}/confirm",
    response_model=ExecutionReportDraftResponse,
    summary="Confirm execution report draft and record progress update",
)
def confirm_execution_report_draft(
    project_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SUPERVISOR OWNER ONLY: Transactionally confirms an execution report draft,
    invokes the Phase 5 execution service with source_type='AI_CHAT', and sets draft status='CONFIRMED'.
    """
    verify_project_access(project_id, current_user, db)

    if current_user.role != "SUPERVISOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors can confirm execution progress updates.",
        )

    draft = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.id == draft_id,
            ExecutionReportDraft.project_id == project_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution report draft #{draft_id} not found.",
        )

    if draft.reported_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only confirm your own execution report drafts.",
        )

    # Idempotency check
    if draft.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Execution report draft #{draft_id} is already in status '{draft.status}' and cannot be confirmed.",
        )

    if not draft.matched_activity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm draft: No schedule activity is linked. Select an activity first.",
        )

    # Construct Phase 5 progress request
    report_req = ProgressReportRequest(
        update_type=UpdateTypeEnum(draft.update_type),
        reported_date=draft.reported_date,
        progress_percentage=draft.progress_percentage if draft.update_type in ["PROGRESS", "START"] else None,
        remarks=draft.remarks,
    )

    # Execute Phase 5 execution update transactionally with source_type="AI_CHAT"
    process_progress_update(
        db=db,
        project_id=project_id,
        activity_id=draft.matched_activity_id,
        user=current_user,
        report_req=report_req,
        source_type="AI_CHAT",
    )

    # Mark draft as CONFIRMED
    draft.status = "CONFIRMED"
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)

    return build_draft_response(db, draft)


@router.post(
    "/{project_id}/ai/progress-drafts/{draft_id}/cancel",
    response_model=ExecutionReportDraftResponse,
    summary="Cancel/reject an execution report draft",
)
def cancel_execution_report_draft(
    project_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SUPERVISOR OWNER ONLY: Rejects an execution report draft without making DB updates."""
    verify_project_access(project_id, current_user, db)

    if current_user.role != "SUPERVISOR":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only supervisors can cancel report drafts.")

    draft = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.id == draft_id,
            ExecutionReportDraft.project_id == project_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft #{draft_id} not found.")

    if draft.reported_by_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel your own drafts.")

    draft.status = "REJECTED"
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)

    return build_draft_response(db, draft)


@router.post(
    "/{project_id}/ai/progress-drafts/{draft_id}/select-activity",
    response_model=ExecutionReportDraftResponse,
    summary="Manually assign activity to execution report draft",
)
def select_draft_activity(
    project_id: int,
    draft_id: int,
    req: SelectActivityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SUPERVISOR OWNER ONLY: Links a specific discipline-authorized activity to the report draft."""
    project, assigned_discipline = verify_project_access(project_id, current_user, db)

    if current_user.role != "SUPERVISOR":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only supervisors can update report drafts.")

    draft = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.id == draft_id,
            ExecutionReportDraft.project_id == project_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft #{draft_id} not found.")

    if draft.reported_by_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own drafts.")

    # Validate activity belongs to project and matches Supervisor's assigned discipline
    activity = (
        db.query(Activity)
        .filter(Activity.project_id == project_id, Activity.id == req.activity_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity #{req.activity_id} not found.")

    verify_supervisor_discipline_authorization(current_user, activity, project, db)

    draft.matched_activity_id = activity.id
    draft.match_status = "MANUALLY_SELECTED"
    draft.match_confidence = None
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)

    return build_draft_response(db, draft)


@router.post(
    "/{project_id}/ai/progress-drafts/{draft_id}/flag-planner-review",
    response_model=ExecutionReportDraftResponse,
    summary="Flag an unmatched report draft for Planner Review",
)
def flag_draft_for_planner_review(
    project_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Flags an unmatched or low-confidence report draft for Planner Review."""
    verify_project_access(project_id, current_user, db)

    draft = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.id == draft_id,
            ExecutionReportDraft.project_id == project_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft #{draft_id} not found.")

    draft.status = "NEEDS_PLANNER_REVIEW"
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)

    return build_draft_response(db, draft)


@router.get(
    "/{project_id}/ai/progress-drafts/{draft_id}",
    response_model=ExecutionReportDraftResponse,
    summary="Get details of an execution report draft",
)
def get_execution_report_draft(
    project_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Gets execution report draft details."""
    verify_project_access(project_id, current_user, db)

    draft = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.id == draft_id,
            ExecutionReportDraft.project_id == project_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft #{draft_id} not found.")

    return build_draft_response(db, draft)


# Existing AI Conversation endpoints remain identical
@router.get(
    "/{project_id}/ai/conversations",
    response_model=List[AIConversationListItem],
    summary="List all AI conversations for current user in project",
)
def list_ai_conversations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve history of AI conversation sessions for current user in project."""
    verify_project_access(project_id, current_user, db)

    conversations = (
        db.query(AIConversation)
        .filter(
            AIConversation.project_id == project_id,
            AIConversation.user_id == current_user.id,
        )
        .order_by(AIConversation.updated_at.desc())
        .all()
    )

    results = []
    for c in conversations:
        msgs = c.messages or []
        last_preview = msgs[-1].content[:60] + "..." if msgs and len(msgs[-1].content) > 60 else (msgs[-1].content if msgs else None)
        results.append(
            AIConversationListItem(
                id=c.id,
                project_id=c.project_id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=len(msgs),
                last_message_preview=last_preview,
            )
        )
    return results


@router.get(
    "/{project_id}/ai/conversations/{conversation_id}",
    response_model=AIConversationResponse,
    summary="Get detailed AI conversation history",
)
def get_ai_conversation(
    project_id: int,
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all messages in a specific AI conversation."""
    verify_project_access(project_id, current_user, db)

    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.project_id == project_id,
            AIConversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found.",
        )

    # Pre-fetch drafts associated with this conversation & project to reconstruct Phase 8 cards safely
    drafts = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.conversation_id == conversation_id,
            ExecutionReportDraft.project_id == project_id,
        )
        .all()
    )
    draft_map = {d.id: d for d in drafts}

    msg_responses = []
    for msg in conversation.messages:
        msg_resp = AIMessageResponse.model_validate(msg)
        if msg.role == "ASSISTANT" and msg.metadata_json:
            try:
                meta = json.loads(msg.metadata_json)
                if isinstance(meta, dict) and "draft_id" in meta:
                    d_id = meta["draft_id"]
                    draft_obj = draft_map.get(d_id)
                    if not draft_obj:
                        draft_obj = (
                            db.query(ExecutionReportDraft)
                            .filter(
                                ExecutionReportDraft.id == d_id,
                                ExecutionReportDraft.project_id == project_id,
                            )
                            .first()
                        )
                    if draft_obj:
                        msg_resp.draft = build_draft_response(db, draft_obj)
            except Exception:
                pass
        msg_responses.append(msg_resp)

    return AIConversationResponse(
        id=conversation.id,
        project_id=conversation.project_id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=msg_responses,
    )


@router.delete(
    "/{project_id}/ai/conversations/{conversation_id}",
    summary="Delete an AI conversation",
)
def delete_ai_conversation(
    project_id: int,
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an AI conversation and its message history."""
    verify_project_access(project_id, current_user, db)

    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.project_id == project_id,
            AIConversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found.",
        )

    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}
