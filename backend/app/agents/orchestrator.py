"""Orchestrator Agent — 意图识别、Agent路由、学习规划."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from app.llm.gateway import gateway, LLMResponse
from app.memory.session import session_memory


INTENT_CLASSIFY_PROMPT = """你是一个学习意图分类器。分析学生的输入，输出JSON格式的分类结果。

分类规则：
- "learn": 请求讲解知识点、答疑解惑、理解概念 → agent: "stem"或"liberal_arts"
- "practice": 请求做题练习、刷题 → agent: "stem"或"liberal_arts"
- "exam": 请求考试、组卷、模拟测试、批改 → agent: "exam"
- "review": 请求复习、错题回顾、总结 → agent: "stem"或"liberal_arts"
- "other": 闲聊或其他无关话题

学科判断 (subject):
- "math": 数学相关问题（计算、函数、几何、代数等）
- "physics": 物理（力学、电学、光学、热学等）
- "chemistry": 化学（方程式、元素、反应等）
- "biology": 生物（细胞、遗传、生态等）
- "chinese": 语文（诗词、文言文、作文、阅读等）
- "english": 英语（单词、语法、阅读、写作等）
- "history": 历史（事件、年代、人物等）
- "politics": 政治（理论、时事、法律等）

输出格式（只输出JSON，不要其他内容）：
{"intent": "learn", "subject": "math", "agent": "stem", "knowledge_points": ["知识点1", "知识点2"]}"""


@dataclass
class IntentResult:
    intent: str  # learn | practice | exam | review | other
    subject: str
    agent: str  # stem | liberal_arts | exam
    knowledge_points: list[str]


class OrchestratorAgent:
    """总管Agent：意图识别→Agent路由→上下文组装."""

    async def classify_intent(self, user_input: str) -> IntentResult:
        """Classify user intent using LLM."""
        messages = [
            {"role": "system", "content": INTENT_CLASSIFY_PROMPT},
            {"role": "user", "content": user_input},
        ]
        resp = await gateway.chat(messages, temperature=0.1, max_tokens=256)

        try:
            data = json.loads(resp.content.strip().removeprefix("```json").removesuffix("```"))
            return IntentResult(
                intent=data.get("intent", "learn"),
                subject=data.get("subject", "math"),
                agent=data.get("agent", "stem"),
                knowledge_points=data.get("knowledge_points", []),
            )
        except (json.JSONDecodeError, KeyError):
            return IntentResult(
                intent="learn", subject="math", agent="stem", knowledge_points=[]
            )

    def get_system_prompt(self, intent: IntentResult) -> str:
        """Generate system prompt based on intent and subject."""
        prompts = {
            "stem": {
                "math": "你是一位专业的初中/高中数学老师。请用清晰的分步方法讲解数学问题。对于计算题使用5步法（审题→列式→计算→检查→答语）。鼓励学生思考，不要直接给答案。",
                "physics": "你是一位专业的初中/高中物理老师。擅长受力分析、电路分析和第一性原理讲解。请用生活中的例子帮助理解物理概念。",
                "chemistry": "你是一位专业的初中/高中化学老师。擅长方程式配平、元素周期表和实验讲解。",
                "biology": "你是一位专业的初中/高中生物老师。擅长概念讲解和流程图说明。",
            },
            "liberal_arts": {
                "chinese": "你是一位专业的初中/高中语文老师。对于诗词用意象→手法→情感三层分析法，作文用三明治反馈法（肯定+建议+鼓励），文言文逐句翻译。",
                "english": "你是一位专业的初中/高中英语老师。单词用词根拆解+例句+记忆法，语法讲清规则和例外，阅读教方法，写作给模板和范文。",
                "history": "你是一位专业的初中/高中历史老师。用原因→经过→影响三段式分析历史事件，联系时政。",
                "politics": "你是一位专业的初中/高中政治老师。用理论→材料→结论三段式讲解大题。",
            },
            "exam": {
                "default": "你是一位专业的考试辅导老师。帮助学生分析试卷结构、制定复习计划、进行模拟测试。",
            },
        }

        group = prompts.get(intent.agent, prompts["stem"])
        subj_prompt = group.get(intent.subject, list(group.values())[0] if group else "")

        base = f"""{subj_prompt}

当前学生是初中/高中学生，使用教材版本为人教版。
请用中文回答，语气亲切鼓励。如果学生在做题，请引导他们自己思考，而不是直接给答案。
当学生答对时给予肯定；答错时分析错因（概念未掌握/公式套错/计算粗心/单位遗漏/审题偏差），并给出解题思路。"""
        return base


orchestrator = OrchestratorAgent()
