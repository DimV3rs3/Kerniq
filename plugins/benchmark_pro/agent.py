from typing import Any, Dict, List, Optional, Tuple
import time
import json
from pathlib import Path
from uuid import UUID

from Kerniq.interfaces.models import Message, MessageRole, ModelRequest, ModelResponse, GenerationOptions, ToolCall
from Kerniq.interfaces.providers import ModelProvider

class BenchmarkAgent:
    """
    An autonomous agent loop designed for benchmarking. 
    It uses a ModelProvider to interact with the LLM and executes tools 
    within a strictly isolated workspace.
    """
    def __init__(
        self, 
        provider: ModelProvider, 
        model_id: str, 
        system_prompt: str, 
        task: str, 
        workspace_root: Path,
        tools: List[Dict[str, Any]],
        options: Optional[GenerationOptions] = None
    ):
        self.provider = provider
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.task = task
        self.workspace_root = workspace_root
        self.tools = tools
        self.options = options or GenerationOptions()
        
        self.messages: List[Message] = []
        self.iterations = 0
        self.tool_calls_count = 0
        self.security_denials = 0
        self.compaction_count = 0
        
        # Metrics storage
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.reasoning_tokens = 0
        self.gen_speeds = [] # tokens/sec

    def _build_initial_messages(self):
        # System prompt
        self.messages.append(Message(role=MessageRole.SYSTEM, content=self.system_prompt))
        
        # Task description
        user_content = (
            f"BENCHMARK TASK:\n{self.task}\n\n"
            f"You are operating in an isolated workspace: {self.workspace_root}\n"
            "Use the provided tools to complete the task. When finished, respond with 'TASK_COMPLETE'."
        )
        self.messages.append(Message(role=MessageRole.USER, content=user_content))

    async def run(self, max_iterations: int, max_tools: int, timeout_seconds: float) -> Tuple[str, Dict[str, Any]]:
        self._build_initial_messages()
        start_time = time.perf_counter()
        
        while self.iterations < max_iterations and self.tool_calls_count < max_tools:
            if (time.perf_counter() - start_time) > timeout_seconds:
                return "timeout", self._get_metrics()

            self.iterations += 1
            
            # Prepare request
            request = ModelRequest(
                messages=self.messages,
                options=self.options,
                tools=self.tools,
                session_id=UUID(int=0), # Dummy ID for benchmark
                metadata={"workspace": str(self.workspace_root)}
            )

            try:
                gen_start = time.perf_counter()
                response: ModelResponse = await self.provider.generate(request)
                gen_end = time.perf_counter()
                
                # Update metrics
                if response.usage:
                    self.total_prompt_tokens += (response.usage.prompt_tokens or 0)
                    self.total_completion_tokens += (response.usage.completion_tokens or 0)
                    # Reasoning tokens are often in metadata or usage depending on provider
                    self.reasoning_tokens += response.metadata.get("reasoning_tokens", 0)
                
                duration = gen_end - gen_start
                if duration > 0 and (response.usage and response.usage.completion_tokens):
                    self.gen_speeds.append(response.usage.completion_tokens / duration)

                # Process messages
                for msg in response.messages:
                    self.messages.append(msg)
                    
                    if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
                        # Handle Tool Calls
                        for tc in msg.tool_calls:
                            self.tool_calls_count += 1
                            result = await self._execute_tool(tc)
                            
                            self.messages.append(Message(
                                role=MessageRole.TOOL,
                                content=str(result),
                                tool_call_id=tc.id
                            ))
                        
                        # After tools, we loop back to the model
                        continue 
                    
                    if msg.role == MessageRole.ASSISTANT and "TASK_COMPLETE" in msg.content:
                        return "success", self._get_metrics()

            except Exception as e:
                return f"error: {str(e)}", self._get_metrics()

        return "limit_reached", self._get_metrics()

    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        # In a real implementation, this would call Kerniq's internal tool registry
        # but wrap the arguments to ensure they stay within self.workspace_root.
        # For now, we simulate the execution or delegate to the provider if supported.
        try:
            # Logic to map tool_call.name -> actual function and execute it in workspace
            # This part will be integrated with Kerniq's ToolRegistry in engine.py
            return f"Executed {tool_call.name} in {self.workspace_root}"
        except Exception as e:
            self.security_denials += 1
            return f"Error executing tool: {str(e)}"

    def _get_metrics(self) -> Dict[str, Any]:
        avg_speed = sum(self.gen_speeds) / len(self.gen_speeds) if self.gen_speeds else 0
        total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        reasoning_pct = (self.reasoning_tokens / total_tokens * 100) if total_tokens > 0 else 0
        
        return {
            "iterations": self.iterations,
            "tool_calls": self.tool_calls_count,
            "security_denials": self.security_denials,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "avg_gen_speed": avg_speed,
            "reasoning_pct": reasoning_pct,
        }
