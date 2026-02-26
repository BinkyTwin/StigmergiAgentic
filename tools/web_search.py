"""Infrastructure tool for provider-backed web search."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.marker import Marker
from core.tool_registry import ActionResult, Tool


STATE_PROGRESS = {
    "pending": "active",
    "active": "completed",
    "completed": "verified",
    "verified": "terminal",
}


class WebSearchTool(Tool):
    """Run web search via configured provider and store normalized results."""

    action_type = "web_search"

    def __init__(self, *, config: dict[str, Any]) -> None:
        tools_cfg = dict(config.get("tools", {}))
        self.provider = str(tools_cfg.get("web_search_provider", "none")).strip().lower()
        self.default_max_results = int(tools_cfg.get("web_search_max_results", 5))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions", [])
        if not isinstance(raw, (list, tuple, set)):
            return False
        return self.action_type in {str(item) for item in raw}

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        query = str(marker.payload.get("query", "")).strip()
        if not query:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_query"},
            )

        max_results = int(marker.payload.get("max_results", self.default_max_results))

        try:
            if self.provider == "none":
                results: list[dict[str, str]] = []
                provider_disabled = True
            elif self.provider == "tavily":
                results = self._search_tavily(query=query, max_results=max_results)
                provider_disabled = False
            elif self.provider == "serper":
                results = self._search_serper(query=query, max_results=max_results)
                provider_disabled = False
            else:
                return ActionResult(
                    action_type=self.action_type,
                    metadata={"failed": True, "reason": f"unsupported_provider:{self.provider}"},
                )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": str(exc)},
            )

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["last_search"] = {
            "query": query,
            "provider": self.provider,
            "provider_disabled": provider_disabled,
            "results": results,
        }
        updated.payload = payload
        updated.state = STATE_PROGRESS.get(updated.state, updated.state)
        updated.intensity = max(0.1, float(updated.intensity) - 0.05)

        return ActionResult(action_type=self.action_type, marker_updates=[updated])

    def _search_tavily(self, *, query: str, max_results: int) -> list[dict[str, str]]:
        api_key = os.environ.get("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise ValueError("missing_api_key:TAVILY_API_KEY")

        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
        }
        raw = self._post_json(
            url="https://api.tavily.com/search",
            payload=payload,
            headers={"Content-Type": "application/json"},
        )
        parsed = json.loads(raw or "{}")
        rows = parsed.get("results", [])
        normalized: list[dict[str, str]] = []
        for row in rows[:max_results]:
            if not isinstance(row, dict):
                continue
            normalized.append(
                {
                    "title": str(row.get("title", "")),
                    "url": str(row.get("url", "")),
                    "snippet": str(row.get("content", "")),
                }
            )
        return normalized

    def _search_serper(self, *, query: str, max_results: int) -> list[dict[str, str]]:
        api_key = os.environ.get("SERPER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("missing_api_key:SERPER_API_KEY")

        payload = {"q": query, "num": max_results}
        raw = self._post_json(
            url="https://google.serper.dev/search",
            payload=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": api_key,
            },
        )
        parsed = json.loads(raw or "{}")
        rows = parsed.get("organic", [])
        normalized: list[dict[str, str]] = []
        for row in rows[:max_results]:
            if not isinstance(row, dict):
                continue
            normalized.append(
                {
                    "title": str(row.get("title", "")),
                    "url": str(row.get("link", "")),
                    "snippet": str(row.get("snippet", "")),
                }
            )
        return normalized

    def _post_json(self, *, url: str, payload: dict[str, Any], headers: dict[str, str]) -> str:
        body = json.dumps(payload).encode("utf-8")
        request = Request(url=url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            raise ValueError(f"http_error:{exc.code}") from exc
        except URLError as exc:
            raise ValueError(f"network_error:{exc.reason}") from exc
