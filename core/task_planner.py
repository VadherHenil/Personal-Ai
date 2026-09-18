"""Small, transparent task-planning model used by Friday's planning mode."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import uuid


@dataclass
class PlanStep:
    id: str
    title: str
    status: str = "pending"


def create_plan(request: str) -> dict:
    text = str(request or "").strip()
    if not text:
        raise ValueError("A task request is required")
    parts = [part.strip(" .") for part in re.split(r"\s*(?:then|after that|and then|;|\n)\s*", text, flags=re.I) if part.strip()]
    if len(parts) == 1:
        parts = [f"Understand: {text}", f"Execute: {text}", "Verify the result and report back"]
    steps = [PlanStep(uuid.uuid4().hex[:8], part[:180]) for part in parts[:12]]
    return {"id": uuid.uuid4().hex, "request": text[:1000], "status": "active", "steps": [asdict(step) for step in steps]}


def advance_plan(plan: dict) -> dict:
    for step in plan.get("steps", []):
        if step.get("status") == "pending":
            step["status"] = "completed"
            break
    if plan.get("steps") and all(step.get("status") == "completed" for step in plan["steps"]):
        plan["status"] = "completed"
    return plan
