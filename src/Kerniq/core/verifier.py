from abc import ABC, abstractmethod
from typing import Any, Optional, List
from pydantic import BaseModel
from ..interfaces.errors import ValidationError

class VerificationResult(BaseModel):
    passed: bool
    message: str
    evidence: Optional[List[str]] = None
    score: float = 1.0  # 0.0 to 1.0

class Verifier(ABC):
    @abstractmethod
    async def verify(self, task_goal: str, context: Any, workspace: str) -> VerificationResult:
        """
        Verify if the task goal has been achieved based on the current state of the workspace and context.
        """
        pass

class BasicVerifier(Verifier):
    def __init__(self, check_files: List[str] = None):
        self.check_files = check_files or []

    async def verify(self, task_goal: str, context: Any, workspace: str) -> VerificationResult:
        # Simple verification: if specific files are expected to exist, check them.
        # In a real scenario, this would be more complex (e.g., running tests).
        import os
        from pathlib import Path
        
        missing_files = []
        for f in self.check_files:
            if not (Path(workspace) / f).exists():
                missing_files.append(f)
        
        if missing_files:
            return VerificationResult(
                passed=False, 
                message=f"Missing expected files: {', '.join(missing_files)}",
                evidence=[f"File {f} not found" for f in missing_files],
                score=0.0
            )
        
        return VerificationResult(
            passed=True, 
            message="Task goals verified successfully.",
            score=1.0
        )
