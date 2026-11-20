"""Monotonic document versions for the OpenSearch product projection.

Product documents are rebuilt from authoritative PostgreSQL state (Strategy B),
so the correct ordering key is *when that state was read*, not the version
counter of whichever aggregate (product, listing, inventory) triggered the sync.
Those counters live in unrelated number spaces; using them with
``version_type=external_gte`` caused valid stock and price updates to be
rejected with 409 and silently dropped.

``snapshot_version()`` returns microseconds since the epoch, captured *before*
the database read. A document built from a later snapshot therefore always has
a higher version and wins; a document built from an older snapshot that
arrives late is rejected as stale, which is exactly the desired behaviour.
"""

from __future__ import annotations

import time


def snapshot_version() -> int:
    """Return a strictly increasing-enough external version (epoch microseconds)."""
    return time.time_ns() // 1_000
