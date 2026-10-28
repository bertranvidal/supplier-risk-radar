"""Forma de la respuesta que le pedimos al LLM (y que validamos con Pydantic)."""
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

EVENT_TYPES = [
    "Natural disaster",
    "Fire / plant incident",
    "Labour strike",
    "Logistics disruption",
    "Quality recall",
    "Regulatory action",
    "Export restriction",
    "Utility outage",
    "Financial distress",
    "Leadership change",
    "Acquisition by competitor",
    "Cyber attack",
    "Geopolitical / sanctions",
    "Other risk",
    "Positive news",
    "Not relevant",
]


IMPACTS = ["none", "delay", "stoppage"]
DURATIONS = ["short", "long", "unknown"]


class Verdict(BaseModel):
    event_type: str = Field(description="one of the allowed event types")
    is_risk: bool
    supply_impact: Literal["none", "delay", "stoppage"] = "none"
    duration: Literal["short", "long", "unknown"] = "unknown"
    affected_supplier_ids: List[str] = []
    confidence: Literal["high", "medium", "low"] = "medium"
    reasoning: str = ""

    @field_validator("supply_impact", "duration", "confidence", mode="before")
    @classmethod
    def _lower(cls, v):
        return str(v).strip().lower()

    @field_validator("affected_supplier_ids", mode="before")
    @classmethod
    def _ids(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            v = v.replace(",", ";").split(";")
        return [str(x).strip().upper() for x in v if str(x).strip()]

    @field_validator("event_type", mode="before")
    @classmethod
    def _event(cls, v):
        v = str(v).strip()
        for e in EVENT_TYPES:
            if e.lower() == v.lower():
                return e
        return v or "Other risk"
