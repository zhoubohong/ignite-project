"""Question bank models with pgvector embedding."""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qtype: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # single_choice|multi_choice|true_false|fill_blank|short_answer|calculation|cloze|reading
    subject: Mapped[str] = mapped_column(String(16), nullable=False)
    grade_level: Mapped[str] = mapped_column(String(16), default="7")
    knowledge_points: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"A":"...", "B":"..."}
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="llm")  # llm|manual|textbook
    embedding: Mapped[Vector] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
