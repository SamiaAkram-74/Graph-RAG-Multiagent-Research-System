"""
Planner Agent — understands the user's research question, decomposes it
into sub-questions, and decides which agents/tools are needed.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import (
    AgentRole,
    AgentMessage,
    SubQuestion,
    TaskPlan,
)


_PLANNER_SYSTEM_PROMPT = """\
You are the Planner Agent in a multi-agent research system called GraphRAG-MARS.
Your job is to:
1. Understand the user's complex research question.
2. Break it down into smaller, manageable sub-questions.
3. For each sub-question, determine which agents should handle it.

Available agents:
- vector_retrieval: Retrieves semantically similar document chunks from a vector database.
- graph_retrieval: Retrieves entity relationships from a knowledge graph.
- web_research: Searches the web for current information.
- reasoning: Synthesises and reasons over collected evidence.

Return your response as valid JSON with this exact structure:
{
  "sub_questions": [
    {
      "id": "sq1",
      "question": "...",
      "required_agents": ["vector_retrieval", "graph_retrieval"],
      "priority": 1,
      "dependencies": []
    }
  ],
  "execution_order": ["sq1", "sq2", ...],
  "estimated_complexity": "low|medium|high"
}

Think step by step. Make sure sub-questions cover different aspects of the original question.
Include dependencies when one sub-question depends on results of another.
"""


class PlannerAgent(BaseAgent):
    """Decomposes a research question into an execution plan."""

    def __init__(self, llm=None):
        super().__init__(role=AgentRole.PLANNER, llm=llm)

    def get_system_prompt(self) -> str:
        return _PLANNER_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {"question": "...", "include_web_search": True}
        Output payload: {"task_plan": TaskPlan.model_dump()}
        """
        question = message.payload.get("question", message.content)
        include_web = message.payload.get("include_web_search", True)

        prompt = self._build_prompt(question, include_web)
        raw = self.call_llm(prompt, temperature=0.1)
        plan_data = self._parse_response(raw, question)
        logger.info(f"Planner created {len(plan_data.sub_questions)} sub-questions")

        return self.create_message(
            content=f"Plan created with {len(plan_data.sub_questions)} sub-tasks",
            receiver=AgentRole.REASONING,
            payload={"task_plan": plan_data.model_dump()},
        )

    def _build_prompt(self, question: str, include_web: bool) -> str:
        agents_available = (
            "vector_retrieval, graph_retrieval, reasoning"
        )
        if include_web:
            agents_available += ", web_research"

        return (
            f"Research question:\n{question}\n\n"
            f"Available agents: {agents_available}\n"
            "Create a plan to answer this question."
        )

    def _parse_response(self, raw: str, question: str) -> TaskPlan:
        """Parse the LLM JSON response with fallback."""
        try:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            text_to_parse = json_match.group(1).strip() if json_match else raw.strip()
            data = json.loads(text_to_parse)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Planner LLM response was not valid JSON, creating single-task plan")
            data = {
                "sub_questions": [{
                    "id": "sq1",
                    "question": question,
                    "required_agents": [
                        AgentRole.VECTOR_RETRIEVAL.value,
                        AgentRole.GRAPH_RETRIEVAL.value,
                    ],
                    "priority": 1,
                    "dependencies": [],
                }],
                "execution_order": ["sq1"],
                "estimated_complexity": "medium",
            }

        sub_questions = [SubQuestion(**sq) for sq in data.get("sub_questions", [])]
        return TaskPlan(
            original_question=question,
            sub_questions=sub_questions,
            execution_order=data.get("execution_order", [sq.id for sq in sub_questions]),
            estimated_complexity=data.get("estimated_complexity", "medium"),
        )
