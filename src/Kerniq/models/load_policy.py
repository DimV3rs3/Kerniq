"""Decide how to load a model. Shells only display this decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .identity import same_model

# What automatic mode may do. The dropdown default is a notice, not a load.
LOAD_ACTIONS = ("alongside", "unload_idle", "unload_busy", "notify")
DEFAULT_LOAD_ACTION = "notify"


@dataclass
class LoadChoice:
    id: str
    label: str

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label}


@dataclass
class LoadPlan:
    selected: str
    loaded: List[str] = field(default_factory=list)
    busy: bool = False
    selected_loaded: bool = False
    status: str = "missing"
    choices: List[LoadChoice] = field(default_factory=list)

    def prompt(self) -> str:
        if self.status != "foreign":
            return ""
        if self.busy:
            return "A model is loaded and in use. It will not be unloaded."
        return "A different model is loaded and it is idle."

    def to_dict(self) -> dict:
        return {
            "selected": self.selected,
            "loaded": list(self.loaded),
            "busy": self.busy,
            "selected_loaded": self.selected_loaded,
            "status": self.status,
            "choices": [choice.to_dict() for choice in self.choices],
            "prompt": self.prompt(),
        }


def plan_model_load(selected: str, loaded: List[str], *, busy: bool = False) -> LoadPlan:
    """What to do when the selected model is not the one already in memory.

    A busy foreign model cannot be unloaded by the manual dialog. An idle one
    can be unloaded, kept alongside the new model, or left alone. No choice is
    required when the selected model is already loaded, or when nothing is loaded.
    """
    want = (selected or "").strip()
    ids = []
    for item in loaded or []:
        text = str(item or "").strip()
        if text and text not in ids:
            ids.append(text)
    selected_loaded = any(same_model(want, mid) for mid in ids) if want else False
    others = [mid for mid in ids if not same_model(want, mid)]
    plan = LoadPlan(
        selected=want,
        loaded=ids,
        busy=bool(busy),
        selected_loaded=selected_loaded,
    )
    if not want:
        plan.status = "missing"
        return plan
    if not others:
        plan.status = "ready" if selected_loaded else "missing"
        return plan
    plan.status = "foreign"
    if busy:
        plan.choices = [
            LoadChoice("alongside", "Load alongside"),
            LoadChoice("cancel", "Don't load"),
        ]
    else:
        plan.choices = [
            LoadChoice("unload", "Unload the idle model and load this one"),
            LoadChoice("alongside", "Load alongside"),
            LoadChoice("cancel", "Cancel"),
        ]
    return plan


def resolve_auto_load(plan: LoadPlan, action: str) -> str:
    """Turn the saved automatic action into a load choice. Never asks.

    ``unload_idle`` unloads only when the other model is idle. A working model
    is left loaded and the new one is loaded beside it.
    ``unload_busy`` unloads even a model that is in use.
    ``notify`` loads nothing and the caller shows a notice.
    """
    chosen = action if action in LOAD_ACTIONS else DEFAULT_LOAD_ACTION
    if plan.status != "foreign":
        return "alongside"
    if chosen == "notify":
        return "notify"
    if chosen == "unload_busy":
        return "unload_busy"
    if chosen == "unload_idle":
        return "alongside" if plan.busy else "unload"
    return "alongside"
