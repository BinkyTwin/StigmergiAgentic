"""Compatibility import for V10 adapter authors.

Adapter implementations should inherit from ``DomainAdapterV10`` here so their
imports stay semantically separate from the runtime contracts package.
"""

from core_v10.contracts import DomainAdapterV10

__all__ = ["DomainAdapterV10"]
