"""
Agent registry.
Central catalogue of all available agents; supports lookup by role.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.schemas import AgentRole

if TYPE_CHECKING:
    from src.core.base_agent import BaseAgent


class AgentRegistry:
    """Registry that maps AgentRole -> agent instance."""

    def __init__(self) -> None:
        self._agents: dict[AgentRole, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance for its role."""
        self._agents[agent.role] = agent

    def get(self, role: AgentRole) -> BaseAgent:
        """Retrieve an agent by its role."""
        if role not in self._agents:
            raise KeyError(f"No agent registered for role: {role.value}")
        return self._agents[role]

    def has(self, role: AgentRole) -> bool:
        return role in self._agents

    def all_agents(self) -> dict[AgentRole, BaseAgent]:
        return dict(self._agents)

    def reset(self) -> None:
        self._agents.clear()


# Global singleton registry
_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
