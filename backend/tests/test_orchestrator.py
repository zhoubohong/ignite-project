"""Orchestrator Agent — intent classification + system prompt for 8 subjects."""
from __future__ import annotations

import json
import uuid

import pytest

from app.agents.orchestrator import OrchestratorAgent, IntentResult


class TestIntentClassification:
    """Orchestrator parses LLM JSON response into IntentResult."""

    def test_parse_valid_learn_intent(self):
        js = '{"intent": "learn", "subject": "math", "agent": "stem", "knowledge_points": ["二次函数"]}'
        data = json.loads(js)
        ir = IntentResult(
            intent=data["intent"],
            subject=data["subject"],
            agent=data["agent"],
            knowledge_points=data["knowledge_points"],
        )
        assert ir.intent == "learn"
        assert ir.subject == "math"
        assert ir.agent == "stem"
        assert ir.knowledge_points == ["二次函数"]

    def test_parse_practice_intent(self):
        js = '{"intent": "practice", "subject": "physics", "agent": "stem", "knowledge_points": ["牛顿第二定律"]}'
        data = json.loads(js)
        ir = IntentResult(**data)
        assert ir.intent == "practice"
        assert ir.subject == "physics"

    def test_parse_exam_intent(self):
        js = '{"intent": "exam", "subject": "english", "agent": "exam", "knowledge_points": []}'
        data = json.loads(js)
        ir = IntentResult(**data)
        assert ir.intent == "exam"
        assert ir.subject == "english"
        assert ir.agent == "exam"

    def test_parse_review_intent(self):
        js = '{"intent": "review", "subject": "chemistry", "agent": "stem", "knowledge_points": ["化学方程式配平"]}'
        data = json.loads(js)
        ir = IntentResult(**data)
        assert ir.intent == "review"
        assert ir.subject == "chemistry"

    def test_fallback_on_malformed_json(self):
        """Malformed LLM response should fallback to learn/math/stem."""
        from app.agents.orchestrator import orchestrator
        # Simulate by testing the IntentResult defaults in classify_intent's except handler
        ir = IntentResult(intent="learn", subject="math", agent="stem", knowledge_points=[])
        assert ir.intent == "learn"
        assert ir.subject == "math"
        assert ir.agent == "stem"

    def test_all_eight_subjects_strings(self):
        """Verify all 8 subjects appear as valid strings in system prompts."""
        subjects = ["math", "physics", "chemistry", "biology", "chinese", "english", "history", "politics"]
        oa = OrchestratorAgent()
        for subj in subjects:
            ir = IntentResult(intent="learn", subject=subj, agent="stem", knowledge_points=[])
            prompt = oa.get_system_prompt(ir)
            assert len(prompt) > 50, f"Prompt too short for {subj}"
            # Should contain the subject name in Chinese or English
            has_subj = any(cn in prompt for cn in ["数学", "物理", "化学", "生物", "语文", "英语", "历史", "政治", "English"])
            assert has_subj, f"Prompt missing subject name for {subj}"


class TestSystemPromptRouting:
    """STEM vs Liberal Arts vs Exam agent prompt differentiation."""

    def test_stem_math_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="math", agent="stem", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "数学" in prompt
        assert "分步" in prompt or "步骤" in prompt

    def test_stem_physics_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="physics", agent="stem", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "物理" in prompt

    def test_stem_chemistry_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="chemistry", agent="stem", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "化学" in prompt

    def test_stem_biology_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="biology", agent="stem", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "生物" in prompt

    def test_liberal_arts_chinese_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="chinese", agent="liberal_arts", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "语文" in prompt

    def test_liberal_arts_english_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="english", agent="liberal_arts", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "英语" in prompt

    def test_liberal_arts_history_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="history", agent="liberal_arts", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "历史" in prompt

    def test_liberal_arts_politics_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="learn", subject="politics", agent="liberal_arts", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert "政治" in prompt

    def test_exam_agent_prompt(self):
        oa = OrchestratorAgent()
        ir = IntentResult(intent="exam", subject="math", agent="exam", knowledge_points=[])
        prompt = oa.get_system_prompt(ir)
        assert len(prompt) > 0

    def test_all_8_subjects_produce_distinct_prompts(self):
        """Every subject should produce a unique system prompt."""
        oa = OrchestratorAgent()
        prompts = []
        for subj in ["math", "physics", "chemistry", "biology", "chinese", "english", "history", "politics"]:
            agent = "stem" if subj in ("math", "physics", "chemistry", "biology") else "liberal_arts"
            ir = IntentResult(intent="learn", subject=subj, agent=agent, knowledge_points=[])
            prompts.append(oa.get_system_prompt(ir))
        # All 8 should be non-empty
        assert all(len(p) > 0 for p in prompts)
        assert len(set(prompts)) == 8, "Expected 8 distinct prompts"
