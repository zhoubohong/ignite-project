"""Chat API — 对话接口，SSE流式输出 + BKT更新."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import orchestrator, IntentResult
from app.db.database import get_db
from app.llm.gateway import gateway
from app.memory.session import session_memory
from app.memory.learning import learning_memory
from app.models.session import StudySession, AnswerRecord

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # None = new session
    user_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    subject: str
    agent: str
    reply: str


@router.post("/send", response_model=ChatResponse)
async def chat_send(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Non-streaming chat endpoint."""
    sid = uuid.UUID(req.session_id) if req.session_id else uuid.uuid4()
    uid = uuid.UUID(req.user_id) if req.user_id else uuid.uuid4()

    # 1. Classify intent
    intent = await orchestrator.classify_intent(req.message)

    # 2. Get L1 session history
    system_prompt = orchestrator.get_system_prompt(intent)
    await session_memory.add_turn(sid, "user", req.message)
    messages = await session_memory.get_messages(sid, system_prompt)

    # 3. LLM response
    resp = await gateway.chat(messages)
    await session_memory.add_turn(sid, "assistant", resp.content)

    # 4. Log session
    session = StudySession(
        id=sid,
        user_id=uid,
        session_type=intent.intent,
        agent_routed=intent.agent,
    )
    db.add(session)
    await db.commit()

    return ChatResponse(
        session_id=str(sid),
        intent=intent.intent,
        subject=intent.subject,
        agent=intent.agent,
        reply=resp.content,
    )


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming chat endpoint."""
    sid = uuid.UUID(req.session_id) if req.session_id else uuid.uuid4()
    uid = uuid.UUID(req.user_id) if req.user_id else uuid.uuid4()

    intent = await orchestrator.classify_intent(req.message)
    system_prompt = orchestrator.get_system_prompt(intent)
    await session_memory.add_turn(sid, "user", req.message)
    messages = await session_memory.get_messages(sid, system_prompt)

    async def event_stream():
        full_reply = ""
        # Send metadata first
        import json as _json
        meta = _json.dumps({
            "session_id": str(sid),
            "intent": intent.intent,
            "subject": intent.subject,
            "agent": intent.agent,
        })
        yield f"data: {meta}\n\n"

        async for token in gateway.chat_stream(messages):
            full_reply += token
            yield f"data: {_json.dumps({'token': token})}\n\n"

        yield "data: [DONE]\n\n"

        # Save reply
        await session_memory.add_turn(sid, "assistant", full_reply)

        session = StudySession(
            id=sid, user_id=uid,
            session_type=intent.intent, agent_routed=intent.agent,
        )
        db.add(session)
        await db.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/answer/check")
async def check_answer(
    question_id: str,
    student_answer: str,
    session_id: str,
    user_id: str,
    subject: str = "math",
    knowledge_point: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Check student answer and update BKT mastery."""
    qid = uuid.UUID(question_id)
    sid = uuid.UUID(session_id)
    uid = uuid.UUID(user_id)

    # Get question
    from app.models.question import Question
    result = await db.execute(
        __import__("sqlalchemy").select(Question).where(Question.id == qid)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    # Simple answer check (exact match for now)
    is_correct = student_answer.strip() == question.answer.strip()

    # Update BKT
    if knowledge_point:
        await learning_memory.update_bkt(
            db, uid, subject, knowledge_point, is_correct
        )

    # Record mistake if wrong
    error_type = ""
    if not is_correct:
        # Simple error classification via LLM
        classify_msg = [
            {"role": "system", "content": "分析学生错因，只回复一个词：concept（概念未掌握）、formula（公式套错）、calculation（计算粗心）、unit（单位遗漏）、reading（审题偏差）"},
            {"role": "user", "content": f"正确答案：{question.answer}\n学生答案：{student_answer}\n题干：{question.stem}"},
        ]
        try:
            r = await gateway.chat(classify_msg, temperature=0.1, max_tokens=32)
            error_type = r.content.strip()
        except Exception:
            error_type = "concept"

        await learning_memory.record_mistake(
            db, uid, qid, student_answer, question.answer, error_type,
        )

    # Log answer
    mastery = await learning_memory.get_mastery(db, uid, knowledge_point)
    record = AnswerRecord(
        session_id=sid,
        user_id=uid,
        question_id=qid,
        student_answer=student_answer,
        is_correct=is_correct,
        mastery_before=mastery.p_learned if mastery else 0.3,
        mastery_after=mastery.p_learned if mastery else 0.3,
    )
    db.add(record)
    await db.commit()

    return {
        "is_correct": is_correct,
        "correct_answer": question.answer,
        "explanation": question.explanation,
        "error_type": error_type,
        "mastery_p_learned": mastery.p_learned if mastery else 0.3,
    }
