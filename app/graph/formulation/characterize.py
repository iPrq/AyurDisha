"""Deterministic formulation characterization — computed from structured context only."""

from __future__ import annotations

from graph.formulation.models import (
    FormulationCharacteristic,
    FormulationContext,
    IdentityStatus,
)
from graph.models import EvidenceKind

_TO_MG = {"mg": 1.0, "g": 1000.0, "kg": 1_000_000.0, "mcg": 0.001}


def characterize(ctx: FormulationContext) -> list[FormulationCharacteristic]:
    chars: list[FormulationCharacteristic] = []
    n = len(ctx.ingredients)
    if n:
        chars.append(
            FormulationCharacteristic(
                key="composition_type",
                label="Composition",
                value="Single-ingredient" if n == 1 else f"Polyherbal ({n} ingredients)",
                evidence_kind=EvidenceKind.CALCULATION,
            )
        )
    masses = [
        (i.quantity or 0) * _TO_MG[i.unit]
        for i in ctx.ingredients
        if i.quantity is not None and i.unit in _TO_MG
    ]
    if n and len(masses) == n:
        total = sum(masses)
        chars.append(
            FormulationCharacteristic(
                key="declared_mass",
                label="Declared mass per unit",
                value=f"{total:g} mg",
                evidence_kind=EvidenceKind.CALCULATION,
            )
        )
    elif n:
        chars.append(
            FormulationCharacteristic(
                key="declared_mass",
                label="Declared mass per unit",
                value="Incomplete — some quantities are missing or not mass-based",
                evidence_kind=EvidenceKind.UNCERTAINTY,
                status=IdentityStatus.INSUFFICIENT_EVIDENCE,
            )
        )
    resolved = sum(1 for i in ctx.ingredients if i.identity_status in (IdentityStatus.CONFIRMED, IdentityStatus.PROBABLE))
    if n:
        chars.append(
            FormulationCharacteristic(
                key="identity_coverage",
                label="Botanical identities resolved",
                value=f"{resolved} of {n}",
                evidence_kind=EvidenceKind.CALCULATION,
                status=IdentityStatus.CONFIRMED if resolved == n else IdentityStatus.HUMAN_REVIEW,
            )
        )
    parts = sorted({i.plant_part for i in ctx.ingredients if i.plant_part})
    if parts:
        chars.append(
            FormulationCharacteristic(
                key="plant_parts", label="Plant parts", value=", ".join(parts), origin="user"
            )
        )
    for key, label in (("dosage_form", "Dosage form"), ("route", "Route"), ("intended_use", "Intended use")):
        value = getattr(ctx, key)
        if value:
            chars.append(FormulationCharacteristic(key=key, label=label, value=str(value), origin="user"))
    if ctx.product_claims:
        chars.append(
            FormulationCharacteristic(
                key="claims", label="Product claims", value=f"{len(ctx.product_claims)} stated", origin="user"
            )
        )
    return chars
