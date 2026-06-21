"""Question bank CRUD API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.question import Question
from app.question_bank.generator import question_generator

router = APIRouter(prefix="/api/questions", tags=["questions"])


class QuestionOut(BaseModel):
    id: str
    qtype: str
    subject: str
    grade_level: str
    difficulty: float
    stem: str
    options: dict
    answer: str
    explanation: str
    knowledge_points: list[str]
    source: str

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    subject: str
    grade_level: str = "7"
    knowledge_points: list[str] = []
    qtypes: list[str] = ["single_choice", "fill_blank", "short_answer"]
    count: int = 3
    difficulty: float = 0.5


class CreateQuestionRequest(BaseModel):
    qtype: str
    subject: str
    grade_level: str = "7"
    difficulty: float = 0.5
    stem: str
    options: dict = {}
    answer: str
    explanation: str = ""
    knowledge_points: list[str] = []


@router.get("/", response_model=list[QuestionOut])
async def list_questions(
    subject: str | None = None,
    grade_level: str | None = None,
    qtype: str | None = None,
    difficulty_min: float | None = None,
    difficulty_max: float | None = None,
    knowledge_point: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List questions with optional filters."""
    stmt = select(Question)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if grade_level:
        stmt = stmt.where(Question.grade_level == grade_level)
    if qtype:
        stmt = stmt.where(Question.qtype == qtype)
    if difficulty_min is not None:
        stmt = stmt.where(Question.difficulty >= difficulty_min)
    if difficulty_max is not None:
        stmt = stmt.where(Question.difficulty <= difficulty_max)
    if knowledge_point:
        stmt = stmt.where(Question.knowledge_points.any(knowledge_point))
    stmt = stmt.order_by(Question.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    questions = result.scalars().all()
    return [QuestionOut(
        id=str(q.id), qtype=q.qtype, subject=q.subject,
        grade_level=q.grade_level, difficulty=q.difficulty,
        stem=q.stem, options=q.options, answer=q.answer,
        explanation=q.explanation, knowledge_points=q.knowledge_points,
        source=q.source,
    ) for q in questions]


@router.post("/generate", response_model=list[QuestionOut])
async def generate_questions(
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate questions via LLM and save to bank."""
    generated = await question_generator.generate(
        subject=req.subject,
        grade_level=req.grade_level,
        knowledge_points=req.knowledge_points,
        qtypes=req.qtypes,
        count=req.count,
        difficulty=req.difficulty,
    )
    results = []
    for gq in generated:
        q = Question(
            qtype=gq.qtype,
            subject=gq.subject,
            grade_level=gq.grade_level,
            difficulty=gq.difficulty,
            stem=gq.stem,
            options=gq.options,
            answer=gq.answer,
            explanation=gq.explanation,
            knowledge_points=gq.knowledge_points,
            source="llm",
        )
        db.add(q)
        await db.flush()
        results.append(QuestionOut(
            id=str(q.id), qtype=q.qtype, subject=q.subject,
            grade_level=q.grade_level, difficulty=q.difficulty,
            stem=q.stem, options=q.options, answer=q.answer,
            explanation=q.explanation, knowledge_points=q.knowledge_points,
            source=q.source,
        ))
    await db.commit()
    return results


@router.post("/", response_model=QuestionOut)
async def create_question(
    req: CreateQuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually create a question."""
    q = Question(
        qtype=req.qtype,
        subject=req.subject,
        grade_level=req.grade_level,
        difficulty=req.difficulty,
        stem=req.stem,
        options=req.options,
        answer=req.answer,
        explanation=req.explanation,
        knowledge_points=req.knowledge_points,
        source="manual",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return QuestionOut(
        id=str(q.id), qtype=q.qtype, subject=q.subject,
        grade_level=q.grade_level, difficulty=q.difficulty,
        stem=q.stem, options=q.options, answer=q.answer,
        explanation=q.explanation, knowledge_points=q.knowledge_points,
        source=q.source,
    )


@router.get("/{question_id}", response_model=QuestionOut)
async def get_question(question_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == uuid.UUID(question_id)))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    return QuestionOut(
        id=str(q.id), qtype=q.qtype, subject=q.subject,
        grade_level=q.grade_level, difficulty=q.difficulty,
        stem=q.stem, options=q.options, answer=q.answer,
        explanation=q.explanation, knowledge_points=q.knowledge_points,
        source=q.source,
    )


@router.delete("/{question_id}")
async def delete_question(question_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == uuid.UUID(question_id)))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    await db.delete(q)
    await db.commit()
    return {"ok": True}
