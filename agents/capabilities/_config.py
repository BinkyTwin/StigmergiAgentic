"""Shared configuration helpers for agent capabilities."""

from __future__ import annotations

from typing import Any

DEFAULT_NON_PY_EXTENSIONS = [
    ".md",
    ".txt",
    ".rst",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
]

DEFAULT_LEGACY_TOKENS = [
    "python2",
    "xrange",
    "iteritems",
    "iterkeys",
    "itervalues",
    "raw_input",
    "has_key",
    "unicode(",
    "long(",
    "urllib2",
    "print >>",
]


def non_python_config(config: dict[str, Any]) -> dict[str, Any]:
    """Parse and normalize the capabilities.non_python config section.

    Returns a dict with all fields used by discover, test, and transform:
      enabled, include_extensions, max_text_file_bytes, legacy_tokens,
      strict_guardrails, pass_confidence, fail_confidence.
    """

    raw = config.get("capabilities", {}).get("non_python", {})

    include_extensions = raw.get("include_extensions", DEFAULT_NON_PY_EXTENSIONS)
    normalized_extensions = sorted(
        {
            ext if str(ext).startswith(".") else f".{ext}"
            for ext in include_extensions
            if isinstance(ext, str) and ext.strip()
        }
    )
    if not normalized_extensions:
        normalized_extensions = list(DEFAULT_NON_PY_EXTENSIONS)

    legacy_tokens = raw.get("legacy_tokens", DEFAULT_LEGACY_TOKENS)
    normalized_legacy_tokens = [
        str(token).strip()
        for token in legacy_tokens
        if isinstance(token, str) and str(token).strip()
    ]
    if not normalized_legacy_tokens:
        normalized_legacy_tokens = list(DEFAULT_LEGACY_TOKENS)

    return {
        "enabled": bool(raw.get("enabled", False)),
        "include_extensions": normalized_extensions,
        "max_text_file_bytes": int(raw.get("max_text_file_bytes", 200_000)),
        "legacy_tokens": normalized_legacy_tokens,
        "strict_guardrails": bool(raw.get("strict_guardrails", True)),
        "pass_confidence": float(raw.get("pass_confidence", 0.85)),
        "fail_confidence": float(raw.get("fail_confidence", 0.4)),
    }
