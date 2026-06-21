"""User & LearnerProfile models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.session import StudySession


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(16), default="student")  # student | parent | teacher
    grade: Mapped[str] = mapped_column(String(16), default="7")  # 7-12
    textbook_version: Mapped[str] = mapped_column(String(32), default="人教版")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sessions: Mapped[list["StudySession"]] = relationship(back_populates="user")


class KnowledgeMastery(Base):
    """L2 Memory: Per-knowledge-point mastery state tracked by BKT."""
    __tablename__ = "knowledge_mastery"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(16), nullable=False)  # math/physics/chemistry/biology/chinese/english/history/politics
    knowledge_point: Mapped[str] = mapped_column(String(256), nullable=False)
    state: Mapped[str] = mapped_column(String(16), default="untouched")  # untouched|exposed|practicing|mastered
    p_learned: Mapped[float] = mapped_column(Float, default=0.3)  # P(L) from BKT
    p_guess: Mapped[float] = mapped_column(Float, default=0.1)  # P(G)
    p_slip: Mapped[float] = mapped_column(Float, default=0.05)  # P(S)
    p_transit: Mapped[float] = mapped_column(Float, default=0.2)  # P(T)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MistakeRecord(Base):
    """Mistake book: wrong answers with error classification."""
    __tablename__ = "mistake_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    student_answer: Mapped[str] = mapped_column(Text, default="")
    correct_answer: Mapped[str] = mapped_column(Text, default="")
    error_type: Mapped[str] = mapped_column(String(32), default="")  # concept/formula/calculation/unit/reading
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
