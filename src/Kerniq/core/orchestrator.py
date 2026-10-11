import json
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from .context import TaskContext
from ..interfaces.models import ModelRequest, ModelResponse, Message, MessageRole, ToolCall, GenerationOptions
from ..interfaces.providers import ModelProvider
from ..tools.registry import ToolRegistry
from ..security.policy import SecurityPolicy, PolicyDecision
from .verifier import Verifier

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, provider: ModelProvider, tool_registry: ToolRegistry, 
                 security_policy: Optional[SecurityPolicy] = None, 
                 verifier: Optional[Verifier] = None,
                 approval_provider: Optional[Any] = None):
        self.provider = provider
        self.tool_registry = tool_registry
        self.security_policy = security_policy
        self.verifier = verifier
        self.approval_provider = approval_provider
        self.max_iterations = 10
        self.generation_options = GenerationOptions()

    async def run(self, context: TaskContext) -> str:
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Orchestration iteration {iteration}/{self.max_iterations}")

            # 1. Prepare request
            request = ModelRequest(
                messages=context.messages,
                session_id=context.session_id,
                tools=self.tool_registry.get_tools_for_model(),
                options=self.generation_options,
            )

            # 2. Get model response
            response = await self.provider.generate(request)
            
            # Add assistant message to context
            for msg in response.messages:
                context.add_message(msg)

            # 3. Check for tool calls
            tool_calls = []
            for msg in response.messages:
                if msg.tool_calls:
                    tool_calls.extend(msg.tool_calls)

            if not tool_calls:
                # Before finishing, try to verify the result if a verifier is present
                if self.verifier:
                    verification = await self.verifier.verify(context.goal, context, context.workspace)
                    if not verification.passed:
                        logger.info(f"Verification failed: {verification.message}")
                        # We can add the verification failure to context and let the model try again
                        context.add_message(Message(
                            role=MessageRole.SYSTEM, 
                            content=f"Verification failed: {verification.message}. Please correct the result."
                        ))
                        continue # Try another iteration

                final_msg = response.messages[-1] if response.messages else None
                return final_msg.content if final_msg else "No response from model"

            # 4. Execute tool calls
            for call in tool_calls:
                logger.info(f"Executing tool: {call.name} with args {call.arguments}")
                
                # Security Check
                if self.security_policy:
                    decision = self.security_policy.evaluate_tool_call(call.name, call.arguments, "medium")
                    if decision == PolicyDecision.DENY:
                        error_msg = f"Security Error: Execution of tool {call.name} is denied by policy."
                        context.add_message(Message(
                            role=MessageRole.TOOL, 
                            content=error_msg, 
                            tool_call_id=call.id
                        ))
                        continue
                    elif decision == PolicyDecision.REQUIRE_APPROVAL:
                        if self.approval_provider:
                            from ..interfaces.approvals import ApprovalRequest
                            import uuid
                            from datetime import datetime
                            
                            app_req = ApprovalRequest(
                                request_id=uuid.uuid4(),
                                tool_id=call.name,
                                arguments=call.arguments,
                                risk_level="medium",
                                description=f"Executing {call.name}",
                                timestamp=datetime.utcnow().isoformat()
                            )
                            app_res = await self.approval_provider.request_approval(app_req)
                            if app_res.decision == "deny":
                                error_msg = f"Security Error: Tool {call.name} was denied by user: {app_res.comment}"
                                context.add_message(Message(
                                    role=MessageRole.TOOL, 
                                    content=error_msg, 
                                    tool_call_id=call.id
                                ))
                                continue
                        else:
                            error_msg = f"Security Error: Tool {call.name} requires manual approval but no provider is configured."
                            context.add_message(Message(
                                role=MessageRole.TOOL, 
                                content=error_msg, 
                                tool_call_id=call.id
                            ))
                            continue

                tool = self.tool_registry.get_tool(call.name)
                if not tool:
                    error_msg = f"Tool {call.name} not found"
                    context.add_message(Message(
                        role=MessageRole.TOOL, 
                        content=error_msg, 
                        tool_call_id=call.id
                    ))
                    continue

                # Execute tool
                result = await tool.execute(call.arguments, context)
                
                # Structured result for the model
                content = result.to_model_content() if hasattr(result, "to_model_content") else (result.human_readable or "")
                context.add_message(Message(
                    role=MessageRole.TOOL,
                    content=content,
                    tool_call_id=call.id,
                    name=tool.name,
                ))

        return "Reached maximum iterations"
