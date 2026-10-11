import pytest
from pathlib import Path
from Kerniq.security.policy import SecurityPolicy, PolicyDecision, RiskLevel
from Kerniq.interfaces.errors import SecurityError, ErrorCode

def test_workspace_boundary_enforcement(tmp_path):
    # Setup workspace
    workspace = tmp_path / "ws"
    workspace.mkdir()
    
    policy = SecurityPolicy(workspace_root=workspace)
    
    # Valid path inside workspace
    valid_path = "test.txt"
    assert policy.validate_path(valid_path).is_relative_to(workspace)
    
    # Invalid path using .. to escape
    invalid_path = "../outside.txt"
    with pytest.raises(SecurityError) as excinfo:
        policy.validate_path(invalid_path)
    assert excinfo.value.code == ErrorCode.PERMISSION_DENIED

def test_absolute_path_escape(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    policy = SecurityPolicy(workspace_root=workspace)
    
    # Absolute path outside workspace
    abs_path = str(tmp_path / "outside.txt")
    with pytest.raises(SecurityError):
        policy.validate_path(abs_path)

def test_terminal_command_blacklist():
    policy = SecurityPolicy(
        workspace_root=Path("."), 
        disallowed_commands=["rm -rf", "format C:"]
    )
    
    assert policy.check_terminal_command("ls -la") == PolicyDecision.ALLOW
    assert policy.check_terminal_command("rm -rf /") == PolicyDecision.DENY
    assert policy.check_terminal_command("echo 'hello' > file.txt") == PolicyDecision.ALLOW

def test_risk_level_evaluation():
    policy = SecurityPolicy(workspace_root=Path("."))
    
    # Low risk should be allowed
    assert policy.evaluate_tool_call("read_file", {}, RiskLevel.LOW) == PolicyDecision.ALLOW
    
    # Critical risk should require approval
    assert policy.evaluate_tool_call("delete_all", {}, RiskLevel.CRITICAL) == PolicyDecision.REQUIRE_APPROVAL
