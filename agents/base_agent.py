"""Abstract base class for stigmergic agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from environment.pheromone_store import PheromoneStore
from stigmergy.llm_client import LLMClient

STIGMERGIC_PREAMBLE = (
    "You are an agent in a stigmergic multi-agent system. "
    "Like ants in a colony, you coordinate with other agents exclusively "
    "through environmental traces (pheromones) — never through direct communication. "
    "You do not know which agent deposited the traces you read, "
    "nor which agent will read the traces you deposit. "
    "The quality and completeness of your traces determines the colony's "
    "collective intelligence. Be thorough: no other agent will ask you "
    "for clarification."
)


class BaseAgent(ABC):
    """Shared lifecycle contract for all agents."""

    def __init__(
        self,
        name: str,
        config: dict[str, Any],
        pheromone_store: PheromoneStore,
        target_repo_path: str | Path,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.name = name
        self.config = config
        self.store = pheromone_store
        self.target_repo_path = Path(target_repo_path)
        self.llm_client = llm_client
        self.logger = logging.getLogger(name)

    @abstractmethod
    def perceive(self) -> dict[str, Any]:
        """Read local environmental state."""

    @abstractmethod
    def should_act(self, perception: dict[str, Any]) -> bool:
        """Return whether this agent should act in this cycle."""

    @abstractmethod
    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        """Produce the action to execute from the current perception."""

    @abstractmethod
    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute the chosen action and return result payload."""

    @abstractmethod
    def deposit(self, result: dict[str, Any]) -> None:
        """Deposit resulting traces into the pheromone environment."""

    def _build_system_prompt(self, role_specific: str) -> str:
        """Combine the stigmergic preamble with a role-specific prompt."""
        preamble = self.config.get("prompts", {}).get("stigmergic_preamble")
        if preamble is None:
            preamble = STIGMERGIC_PREAMBLE
        if not preamble:  # "" disables preamble
            return role_specific
        return f"{preamble}\n\n{role_specific}"

    def run(self) -> bool:
        """Run a full agent cycle; return whether this agent acted."""
        perception = self.perceive()
        if not self.should_act(perception):
            self.logger.debug("[%s] idle", self.name)
            return False

        action = self.decide(perception)
        result = self.execute(action)
        self.deposit(result)
        self.logger.debug("[%s] acted", self.name)
        return True
