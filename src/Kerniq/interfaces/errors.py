from enum import Enum
from typing import Optional

class ErrorCode(str, Enum):
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_REQUEST_FAILED = "provider_request_failed"
    AUTHENTICATION_ERROR = "authentication_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_ARGUMENT_ERROR = "tool_argument_error"
    PERMISSION_DENIED = "permission_denied"
    APPROVAL_DENIED = "approval_denied"
    EXECUTION_TIMEOUT = "execution_timeout"
    OPERATION_CANCELLED = "operation_cancelled"
    PLUGIN_COMPATIBILITY_ERROR = "plugin_compatibility_error"
    PLUGIN_INITIALIZATION_ERROR = "plugin_initialization_error"
    MCP_TRANSPORT_ERROR = "mcp_transport_error"
    STORAGE_ERROR = "storage_error"
    CONTEXT_LIMIT_REACHED = "context_limit_reached"
    ITERATION_LIMIT_REACHED = "iteration_limit_reached"
    VERIFICATION_FAILED = "verification_failed"
    INTERNAL_ERROR = "internal_error"

class PlatformError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict] = None, original_exception: Optional[Exception] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(f"[{code.value}] {message}")

class ConfigurationError(PlatformError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.CONFIGURATION_ERROR, message, details)

class ValidationError(PlatformError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details)

class ProviderError(PlatformError):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict] = None, original_exception: Optional[Exception] = None):
        super().__init__(code, message, details, original_exception)

class ToolError(PlatformError):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict] = None):
        super().__init__(code, message, details)

class SecurityError(PlatformError):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict] = None):
        super().__init__(code, message, details)
