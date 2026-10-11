"""Declarative settings schema for tools and plugins (UI + CLI)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class SettingType(str, Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    SELECT = "select"


class SettingField(BaseModel):
    """One configurable field exposed to UI/CLI."""

    key: str
    label: str
    type: SettingType = SettingType.STRING
    default: Any = None
    description: str = ""
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    options: Optional[List[Dict[str, str]]] = None  # [{value, label}]
    group: str = "general"

    def to_public(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class SettingsSchema(BaseModel):
    """Collection of fields + category metadata for a component."""

    component_id: str
    component_type: str  # "tool" | "plugin"
    title: str
    fields: List[SettingField] = Field(default_factory=list)

    def defaults(self) -> Dict[str, Any]:
        return {f.key: f.default for f in self.fields}

    def to_public(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "title": self.title,
            "fields": [f.to_public() for f in self.fields],
            "defaults": self.defaults(),
        }


def coerce_value(field: SettingField, raw: Any) -> Any:
    if raw is None:
        return field.default
    if field.type == SettingType.BOOL:
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in ("1", "true", "yes", "on")
    if field.type == SettingType.INT:
        v = int(raw)
        if field.minimum is not None:
            v = max(int(field.minimum), v)
        if field.maximum is not None:
            v = min(int(field.maximum), v)
        return v
    if field.type == SettingType.FLOAT:
        v = float(raw)
        if field.minimum is not None:
            v = max(float(field.minimum), v)
        if field.maximum is not None:
            v = min(float(field.maximum), v)
        return v
    if field.type == SettingType.SELECT:
        val = str(raw)
        if field.options:
            allowed = {o["value"] for o in field.options}
            if val not in allowed:
                return field.default
        return val
    return str(raw)
