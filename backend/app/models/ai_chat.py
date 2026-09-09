from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class AIConversation(Base):
    """AI Conversation history entity per project and user."""
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("Project", back_populates="ai_conversations")
    user = relationship("User", back_populates="ai_conversations")
    messages = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AIMessage.id",
    )

    def __repr__(self) -> str:
        return f"<AIConversation id={self.id} title={self.title} project_id={self.project_id}>"


class AIMessage(Base):
    """Single message in an AI conversation."""
    __tablename__ = "ai_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "USER" or "ASSISTANT"
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON-encoded tool calls / sources
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    conversation = relationship("AIConversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<AIMessage id={self.id} role={self.role} conversation_id={self.conversation_id}>"
