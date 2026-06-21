"""LLM-based question generator supporting 6 question types."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from app.llm.gateway import gateway


QUESTION_GEN_PROMPT = """你是一个专业的教育题库出题老师。根据指定的学科、年级和知识点生成高质量题目。

输出格式（严格的JSON）：
{
  "questions": [
    {
      "qtype": "single_choice",
      "stem": "题目题干",
      "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
      "answer": "A",
      "explanation": "详细解析",
      "difficulty": 0.5,
      "knowledge_points": ["关联知识点"]
    }
  ]
}

qtype可选值：single_choice, multi_choice, true_false, fill_blank, short_answer, calculation
difficulty范围：0.0（最易）~ 1.0（最难）"""


@dataclass
class GeneratedQuestion:
    qtype: str
    subject: str
    grade_level: str
    stem: str
    options: dict
    answer: str
    explanation: str
    difficulty: float
    knowledge_points: list[str]


class QuestionGenerator:
    """Generate questions using LLM."""

    async def generate(
        self,
        subject: str,
        grade_level: str,
        knowledge_points: list[str],
        qtypes: list[str] | None = None,
        count: int = 3,
        difficulty: float = 0.5,
    ) -> list[GeneratedQuestion]:
        """Generate questions via LLM."""
        if qtypes is None:
            qtypes = ["single_choice", "fill_blank", "short_answer"]

        qtype_str = "、".join(qtypes)
        kp_str = "、".join(knowledge_points) if knowledge_points else "综合"

        user_prompt = (
            f"请为{grade_level}年级学生生成{count}道{subject}题目。\n"
            f"知识点：{kp_str}\n"
            f"题型：{qtype_str}\n"
            f"难度：{difficulty:.1f}（0-1之间）\n"
            f"要求：题目清晰、答案准确、解析详实。直接输出JSON数组。"
        )

        messages = [
            {"role": "system", "content": QUESTION_GEN_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        resp = await gateway.chat(messages, temperature=0.7, max_tokens=4096)

        try:
            content = resp.content.strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            items = data if isinstance(data, list) else data.get("questions", [])
        except (json.JSONDecodeError, KeyError):
            return []

        results = []
        for item in items[:count]:
            results.append(GeneratedQuestion(
                qtype=item.get("qtype", "single_choice"),
                subject=subject,
                grade_level=grade_level,
                stem=item.get("stem", ""),
                options=item.get("options", {}),
                answer=str(item.get("answer", "")),
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", difficulty),
                knowledge_points=item.get("knowledge_points", knowledge_points),
            ))
        return results


question_generator = QuestionGenerator()
