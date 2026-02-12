"""Abstract base class for stigmergic agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from environment.pheromone_store import PheromoneStore
from stigmergy.llm_client import LLMClient


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
