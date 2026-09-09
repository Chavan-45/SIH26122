import json
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.ai_chat import AIConversation, AIMessage
from app.schemas.ai_chat import (
    AIChatRequest,
    AIChatResponse,
    AIConversationListItem,
    AIConversationResponse,
    AIMessageResponse,
)
from app.core.dependencies import get_current_user
from app.services.project_service import verify_project_access
from app.ai.gemini_provider import run_ai_chat_turn

router = APIRouter(prefix="/projects", tags=["Project AI Assistant"])


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
    Sends an operational query to the AI Assistant for the specified project.
    Executes read-only project tools and enforces role-based discipline scoping.
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

    # Execute AI turn
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

    # Touch conversation timestamp
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
    )


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

    return AIConversationResponse.model_validate(conversation)


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
