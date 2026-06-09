"""GAP-011: ViabilityWeights schema with validation.

Per-sector weights for viability assessment factors.
Defaults match the original hardcoded weights in config/features.py.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class ViabilityWeights(BaseModel):
    """Configurable weights for the four viability assessment factors.

    Each weight controls the contribution of a factor to the composite
    viability score (0-100).  Weights MUST sum to 1.0 (within 0.001
    tolerance).

    Defaults match the canonical distribution:
        modalidade=0.30, timeline=0.25, valor_estimado=0.25, geografia=0.20
    """

    modalidade: float = 0.30
    timeline: float = 0.25
    valor_estimado: float = 0.25
    geografia: float = 0.20

    @model_validator(mode="after")
    def _check_sum(self) -> "ViabilityWeights":
        total = self.modalidade + self.timeline + self.valor_estimado + self.geografia
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Viability weights must sum to 1.0, got {total:.4f} "
                f"(modalidade={self.modalidade}, timeline={self.timeline}, "
                f"valor_estimado={self.valor_estimado}, geografia={self.geografia})"
            )
        return self
