from __future__ import annotations

import json
import os
from enum import Enum


class StrictnessLevel(Enum):
    FLUID = "fluid"
    NORMAL = "normal"
    STRICT = "strict"
    FROZEN = "frozen"


class ViscosityController:
    """Records loop metrics and maps them to a strictness level.

    The composite score reflects how "viscous" (resistant to change) the
    system should be: higher scores indicate more problems and thus a more
    conservative (frozen) retrieval posture.
    """

    _THRESHOLDS: dict[StrictnessLevel, dict] = {
        StrictnessLevel.FLUID: {"mintop": 0.58, "max_hits": 4, "min_overlap": 1},
        StrictnessLevel.NORMAL: {"mintop": 0.62, "max_hits": 3, "min_overlap": 1},
        StrictnessLevel.STRICT: {"mintop": 0.68, "max_hits": 2, "min_overlap": 2},
        StrictnessLevel.FROZEN: {"mintop": 0.75, "max_hits": 1, "min_overlap": 2},
    }

    def __init__(self, store_path: str) -> None:
        self.store_path = store_path
        self.history: list[dict] = []
        self._load()

    # -- public API -------------------------------------------------

    def record(self, metrics: dict) -> None:
        """Record a single loop-metrics snapshot and persist."""
        entry = {
            "success_rate": float(metrics["success_rate"]),
            "error_rate": float(metrics["error_rate"]),
            "contradiction_count": int(metrics["contradiction_count"]),
            "elapsed_secs": float(metrics["elapsed_secs"]),
        }
        self.history.append(entry)
        self._save()

    def compute_signal(self) -> dict:
        """Compute a composite signal from the most recent (≤10) records."""
        recent = self.history[-10:]
        if not recent:
            return {
                "mean_success_rate": 0.0,
                "mean_error_rate": 0.0,
                "total_contradictions": 0,
                "composite_score": 0.0,
            }
        mean_success_rate = sum(r["success_rate"] for r in recent) / len(recent)
        mean_error_rate = sum(r["error_rate"] for r in recent) / len(recent)
        total_contradictions = sum(r["contradiction_count"] for r in recent)
        composite_score = (
            (1 - mean_success_rate) * 0.4
            + mean_error_rate * 0.3
            + min(total_contradictions / 10, 1.0) * 0.3
        )
        return {
            "mean_success_rate": mean_success_rate,
            "mean_error_rate": mean_error_rate,
            "total_contradictions": total_contradictions,
            "composite_score": composite_score,
        }

    def level(self) -> StrictnessLevel:
        """Map the current composite score to a strictness level."""
        score = self.compute_signal()["composite_score"]
        if score < 0.3:
            return StrictnessLevel.FLUID
        if score < 0.5:
            return StrictnessLevel.NORMAL
        if score < 0.7:
            return StrictnessLevel.STRICT
        return StrictnessLevel.FROZEN

    def thresholds(self, level: StrictnessLevel) -> dict:
        """Return recall threshold adjustments for the given level."""
        return dict(self._THRESHOLDS[level])

    # -- persistence ------------------------------------------------

    def _save(self) -> None:
        data = {"history": self.history}
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump(data, f)

    def _load(self) -> None:
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path) as f:
                    data = json.load(f)
                self.history = data.get("history", [])
            except (json.JSONDecodeError, IOError):
                self.history = []
        else:
            self.history = []