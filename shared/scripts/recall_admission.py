#!/usr/bin/env python3
"""Recall-admission JSONL system with hubness gating.

Each retrieval candidate is evaluated against a JSONL ledger that tracks how
many times a given result_id has appeared across all queries (global hit
frequency) and within the same namespace (namespace hit frequency). Candidates
that are "hubs" (high global frequency) with low term overlap and no namespace
match are rejected to prevent irrelevant but popular facts from being injected
into agent context.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    """Return current UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


def _hash_query(query: str) -> str:
    """Return a short SHA-256 hex digest of the query string."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


@dataclass
class AdmissionRecord:
    """A single admission decision for a retrieval candidate."""

    query_hash: str
    result_id: str
    namespace: str
    score: float
    cosine: float
    query_terms: list[str] = field(default_factory=list)
    result_terms: list[str] = field(default_factory=list)
    namespace_match: bool = False
    global_hit_frequency: int = 0
    namespace_hit_frequency: int = 0
    admitted: bool = False
    reject_reason: str | None = None
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdmissionRecord":
        return cls(**data)


class RecallAdmissionLedger:
    """JSONL-backed ledger tracking recall admission decisions with hubness gating.

    The ledger maintains in-memory frequency counters loaded from the JSONL file
    so that ``evaluate`` and ``stats`` are O(1) lookups rather than file re-reads.
    """

    HUB_THRESHOLD: int = 15
    LOW_SCORE_THRESHOLD: float = 0.3
    DEMOTE_SCORE_THRESHOLD: float = 0.4
    OVERLAP_THRESHOLD: float = 0.3

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # In-memory frequency tracking
        self._global_freq: dict[str, int] = {}
        self._namespace_freq: dict[tuple[str, str], int] = {}
        self._records: list[AdmissionRecord] = []
        self._load()

    # ------------------------------------------------------------------ #
    #  Loading                                                            #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        """Load existing JSONL records into memory and rebuild frequency tables."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record = AdmissionRecord.from_dict(data)
                self._records.append(record)
                self._global_freq[record.result_id] = (
                    self._global_freq.get(record.result_id, 0) + 1
                )
                ns_key = (record.result_id, record.namespace)
                self._namespace_freq[ns_key] = (
                    self._namespace_freq.get(ns_key, 0) + 1
                )

    # ------------------------------------------------------------------ #
    #  Evaluation                                                         #
    # ------------------------------------------------------------------ #

    def _term_overlap(self, query_terms: list[str], result_terms: list[str]) -> float:
        """Compute term overlap ratio: |intersection| / len(query_terms)."""
        if not query_terms:
            return 0.0
        qset = set(t.lower() for t in query_terms)
        rset = set(t.lower() for t in result_terms)
        return len(qset & rset) / len(qset)

    def evaluate(
        self,
        query: str,
        result_id: str,
        namespace: str,
        score: float,
        cosine: float,
        query_terms: list[str],
        result_terms: list[str],
        namespace_match: bool,
    ) -> AdmissionRecord:
        """Evaluate a retrieval candidate against hubness gating rules.

        Returns an :class:`AdmissionRecord` with the admission decision and
        frequencies populated. Does NOT write to the ledger — call
        :meth:`write` to persist.
        """
        global_hit_frequency = self._global_freq.get(result_id, 0)
        ns_key = (result_id, namespace)
        namespace_hit_frequency = self._namespace_freq.get(ns_key, 0)
        term_overlap = self._term_overlap(query_terms, result_terms)

        admitted = True
        reject_reason: str | None = None

        # Rule 1: reject hubs with low overlap and no namespace match
        if (
            global_hit_frequency > self.HUB_THRESHOLD
            and term_overlap < self.OVERLAP_THRESHOLD
            and not namespace_match
        ):
            admitted = False
            reject_reason = "hub: high frequency with low overlap"
        # Rule 2: reject low score without namespace match
        elif (
            score < self.LOW_SCORE_THRESHOLD and not namespace_match
        ):
            admitted = False
            reject_reason = "low score without namespace match"
        # Rule 3: demote (still admitted) low score without namespace match
        elif (
            score < self.DEMOTE_SCORE_THRESHOLD and not namespace_match
        ):
            reject_reason = "demoted: low score"

        record = AdmissionRecord(
            query_hash=_hash_query(query),
            result_id=result_id,
            namespace=namespace,
            score=score,
            cosine=cosine,
            query_terms=query_terms,
            result_terms=result_terms,
            namespace_match=namespace_match,
            global_hit_frequency=global_hit_frequency,
            namespace_hit_frequency=namespace_hit_frequency,
            admitted=admitted,
            reject_reason=reject_reason,
            timestamp=_now_iso(),
        )
        return record

    # ------------------------------------------------------------------ #
    #  Writing                                                            #
    # ------------------------------------------------------------------ #

    def write(self, record: AdmissionRecord) -> None:
        """Append an AdmissionRecord to the JSONL file and update in-memory state."""
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict()) + "\n")

        self._records.append(record)
        self._global_freq[record.result_id] = (
            self._global_freq.get(record.result_id, 0) + 1
        )
        ns_key = (record.result_id, record.namespace)
        self._namespace_freq[ns_key] = (
            self._namespace_freq.get(ns_key, 0) + 1
        )

    # ------------------------------------------------------------------ #
    #  Statistics                                                         #
    # ------------------------------------------------------------------ #

    def stats(self) -> dict[str, Any]:
        """Return aggregate statistics about the ledger."""
        total_candidates = len(self._records)
        total_admitted = sum(1 for r in self._records if r.admitted)
        total_rejected = sum(1 for r in self._records if not r.admitted)
        unique_result_ids = len(self._global_freq)
        hub_result_ids = [
            rid for rid, freq in self._global_freq.items()
            if freq > self.HUB_THRESHOLD
        ]
        return {
            "total_candidates": total_candidates,
            "total_admitted": total_admitted,
            "total_rejected": total_rejected,
            "unique_result_ids": unique_result_ids,
            "hub_result_ids": hub_result_ids,
        }

    # ------------------------------------------------------------------ #
    #  Utility                                                            #
    # ------------------------------------------------------------------ #

    @property
    def records(self) -> list[AdmissionRecord]:
        """Return a copy of all loaded records."""
        return list(self._records)

    def reset(self) -> None:
        """Clear in-memory state and delete the JSONL file. Mainly for tests."""
        self._records.clear()
        self._global_freq.clear()
        self._namespace_freq.clear()
        if self.path.exists():
            self.path.unlink()