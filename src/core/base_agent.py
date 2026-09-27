"""
Base agent class.
All agents in the system inherit from this abstract base.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from src.core.schemas import AgentRole, AgentMessage
from src.core.llm import LLMClient, get_llm


class BaseAgent(ABC):
    """Abstract base class for all agents in GraphRAG-MARS."""

    def __init__(self, role: AgentRole, llm: LLMClient | None = None):
        self.role = role
        self.agent_id = str(uuid.uuid4())[:8]
        self.llm = llm or get_llm()
        self.execution_log: list[dict[str, Any]] = []
        logger.info(f"Agent [{self.role.value}] initialised (id={self.agent_id})")

    @abstractmethod
    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Execute the agent's primary task given an incoming message.
        Returns an AgentMessage with results.
        """
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt that defines this agent's persona and instructions."""
        ...

    def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Helper to call the LLM with this agent's system prompt."""
        sys_prompt = system_prompt or self.get_system_prompt()
        start = time.time()
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=sys_prompt,
            temperature=temperature,
        )
        elapsed = time.time() - start
        tokens = self.llm.count_tokens(prompt) + self.llm.count_tokens(response)
        self._log_execution(prompt, response, elapsed, tokens)
        return response

    def _log_execution(
        self, prompt: str, response: str, elapsed: float, tokens: int
    ) -> None:
        """Record execution metadata for evaluation."""
        self.execution_log.append({
            "agent": self.role.value,
            "timestamp": time.time(),
            "prompt_tokens": self.llm.count_tokens(prompt),
            "response_tokens": self.llm.count_tokens(response),
            "total_tokens": tokens,
            "latency_sec": round(elapsed, 3),
        })

    def create_message(
        self,
        content: str,
        receiver: AgentRole | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentMessage:
        """Create an outgoing message from this agent."""
        return AgentMessage(
            sender=self.role,
            receiver=receiver,
            content=content,
            payload=payload or {},
        )

    def get_execution_stats(self) -> dict[str, Any]:
        """Return aggregate execution statistics."""
        if not self.execution_log:
            return {"total_calls": 0, "total_tokens": 0, "total_latency": 0}
        return {
            "total_calls": len(self.execution_log),
            "total_tokens": sum(e["total_tokens"] for e in self.execution_log),
            "total_latency": round(sum(e["latency_sec"] for e in self.execution_log), 3),
            "avg_latency": round(
                sum(e["latency_sec"] for e in self.execution_log) / len(self.execution_log), 3
            ),
        }
