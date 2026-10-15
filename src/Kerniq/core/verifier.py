from abc import ABC, abstractmethod
import ast
from pathlib import Path
from typing import Any, Optional, List
from pydantic import BaseModel

class VerificationResult(BaseModel):
    passed: bool
    message: str
    evidence: Optional[List[str]] = None
    score: float = 1.0  # 0.0 to 1.0


def is_unverified(result: VerificationResult) -> bool:
    return bool(result.passed and result.evidence and "unverified" in result.evidence)


class Verifier(ABC):
    @abstractmethod
    async def verify(self, task_goal: str, context: Any, workspace: str) -> VerificationResult:
        """
        Verify if the task goal has been achieved based on the current state of the workspace and context.
        """
        pass

class BasicVerifier(Verifier):
    """Checks explicit criteria only.

    With no configured checks the result is passed=True and evidence=['unverified']
    so callers can avoid claiming a confirmed success. File existence, substring
    containment, and Python syntax are real checks. A shell test command is not
    invented here.
    """

    def __init__(self, check_files: List[str] | None = None):
        self.check_files = list(check_files or [])

    async def verify(self, task_goal: str, context: Any, workspace: str) -> VerificationResult:
        checks = {}
        if context is not None:
            meta = getattr(context, "metadata", None) or {}
            raw = meta.get("checks") or {}
            if isinstance(raw, dict):
                checks = raw
        files = list(self.check_files) + [str(item) for item in (checks.get("files") or [])]
        contains = checks.get("contains") or {}
        if not isinstance(contains, dict):
            contains = {}
        syntax = [str(item) for item in (checks.get("syntax") or [])]
        if not files and not contains and not syntax:
            return VerificationResult(
                passed=True,
                message=(
                    "No automatic checks were configured. "
                    "The reply was not independently verified against the workspace."
                ),
                evidence=["unverified"],
                score=0.0,
            )

        root = Path(workspace) if workspace else Path(".")
        missing: List[str] = []
        evidence: List[str] = []
        for rel in files:
            path = root / rel
            if path.exists():
                evidence.append(f"exists:{rel}")
            else:
                missing.append(rel)
        for rel, needle in contains.items():
            path = root / str(rel)
            text = ""
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
            if path.is_file() and str(needle) in text:
                evidence.append(f"contains:{rel}")
            else:
                missing.append(f"contains:{rel}")
        for rel in syntax:
            path = root / rel
            if not path.is_file():
                missing.append(f"syntax:{rel}")
                continue
            if path.suffix != ".py":
                evidence.append(f"syntax-skipped:{rel}")
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"))
                evidence.append(f"syntax:{rel}")
            except SyntaxError as exc:
                missing.append(f"syntax:{rel}:{exc.msg}")

        if missing:
            return VerificationResult(
                passed=False,
                message="Checks failed: " + ", ".join(missing),
                evidence=evidence + [f"missing:{item}" for item in missing],
                score=0.0,
            )
        return VerificationResult(
            passed=True,
            message="Configured checks passed.",
            evidence=evidence,
            score=1.0,
        )
