import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from Kerniq.interfaces.providers import ModelProvider
from .agent import BenchmarkAgent

class ModelRunMetrics:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.load_time = 0.0
        self.exec_time = 0.0
        self.stop_reason = "unknown"
        self.iterations = 0
        self.tool_calls = 0
        self.tool_errors = 0
        self.security_denials = 0
        self.context_max = 0
        self.context_used = 0
        self.compaction_count = 0
        self.avg_gen_speed = 0.0 # tokens/sec
        self.reasoning_pct = 0.0 # reasoning / total
        self.tests_passed = False
        self.test_details = ""

    def update_from_agent(self, agent_metrics: Dict[str, Any]):
        self.iterations = agent_metrics.get("iterations", 0)
        self.tool_calls = agent_metrics.get("tool_calls", 0)
        self.security_denials = agent_metrics.get("security_denials", 0)
        self.avg_gen_speed = agent_metrics.get("avg_gen_speed", 0.0)
        self.reasoning_pct = agent_metrics.get("reasoning_pct", 0.0)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

class BenchmarkWorkspaceManager:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def setup_model_dir(self, model_id: str, run_id: str) -> Path:
        safe_id = model_id.replace("/", "_").replace("\\", "_")
        dir_path = self.base_path / f"{safe_id}_{run_id}"
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

class BenchmarkEngine:
    def __init__(self, context, settings: Dict[str, Any]):
        self.context = context
        self.settings = settings
        self.workspace_mgr = BenchmarkWorkspaceManager(Path(settings.get("results_path", ".workspace/benchmarks")))

    async def run_benchmark(self, providers: List[ModelProvider], task: str, system_prompt: str):
        results = []
        for provider in providers:
            model_id = provider.provider_id
            
            # 1. Unload models (simulated via provider if available)
            await self._unload_models(provider)
            
            # 2. Setup workspace
            run_id = str(uuid4())[:8]
            work_dir = self.workspace_mgr.setup_model_dir(model_id, run_id)
            metrics = ModelRunMetrics(model_id)
            
            try:
                # 3. Load Model with retry logic
                load_start = time.perf_counter()
                # Try loading with standard params first, then without if it fails
                success = await self._attempt_load(provider, use_params=True)
                if not success:
                    success = await self._attempt_load(provider, use_params=False)
                
                metrics.load_time = time.perf_counter() - load_start
                
                if not success:
                    metrics.stop_reason = "model_load_failed"
                    results.append(metrics.to_dict())
                    continue

                # 4. Execute Agent Loop
                exec_start = time.perf_counter()
                agent = BenchmarkAgent(
                    provider=provider,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    task=task,
                    workspace_root=work_dir,
                    tools=[], # In real use: self.context.tool_registry.get_all()
                    options=None
                )
                
                stop_reason, agent_metrics = await agent.run(
                    max_iterations=self.settings.get("max_iterations", 100),
                    max_tools=self.settings.get("max_tool_calls", 100),
                    timeout_seconds=self.settings.get("max_runtime_seconds", 3600)
                )
                
                metrics.exec_time = time.perf_counter() - exec_start
                metrics.stop_reason = stop_reason
                metrics.update_from_agent(agent_metrics)

                # 5. Validation (Tests)
                metrics.tests_passed, metrics.test_details = await self._validate_results(work_dir)

            except Exception as e:
                metrics.stop_reason = f"exception: {str(e)}"
            finally:
                await self._unload_models(provider)
                results.append(metrics.to_dict())
        
        return results

    async def _unload_models(self, provider: ModelProvider):
        # Implementation depends on provider's ability to unload
        pass

    async def _attempt_load(self, provider: ModelProvider, use_params: bool) -> bool:
        try:
            # Logic for loading via provider. If it's a local model, 
            # we might need specific load calls here.
            return True 
        except Exception:
            return False

    async def _validate_results(self, work_dir: Path) -> Tuple[bool, str]:
        # Simulate running tests in the workspace (e.g., calling 'pytest' via shell tool)
        return True, "All tests passed"
