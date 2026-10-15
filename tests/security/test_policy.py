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

    assert policy.evaluate_tool_call("read_file", {}, RiskLevel.LOW) == PolicyDecision.ALLOW
    assert policy.evaluate_tool_call("write_file", {}, RiskLevel.MEDIUM) == PolicyDecision.REQUIRE_APPROVAL
    assert policy.evaluate_tool_call("delete_all", {}, RiskLevel.CRITICAL) == PolicyDecision.REQUIRE_APPROVAL


def test_developer_bypass_allows_critical():
    policy = SecurityPolicy(workspace_root=Path("."), auto_approve_up_to="all")

    class Tool:
        name = "run_command"
        tool_id = "run_command"
        risk_level = "critical"
        cfg_auto_accept = False

    assert policy.bypass_all is True
    assert policy.evaluate_tool_call("run_command", {"command": "ls"}, "critical", tool=Tool()) == PolicyDecision.ALLOW
    assert policy.evaluate_tool_call("run_command", {"command": "rm -rf /"}, "critical", tool=Tool()) == PolicyDecision.DENY
    policy = SecurityPolicy(workspace_root=Path("."), auto_approve_up_to="high")

    class Tool:
        name = "run_command"
        tool_id = "run_command"
        risk_level = "critical"
        cfg_auto_accept = True

    decision = policy.evaluate_tool_call("run_command", {"command": "ls"}, "low", tool=Tool())
    assert decision == PolicyDecision.REQUIRE_APPROVAL


def test_auto_accept_skips_non_critical():
    policy = SecurityPolicy(workspace_root=Path("."), auto_approve_up_to="low")

    class Tool:
        name = "delete_file"
        tool_id = "delete_file"
        risk_level = "high"
        cfg_auto_accept = True

    assert policy.evaluate_tool_call("delete_file", {}, "high", tool=Tool()) == PolicyDecision.ALLOW


def test_caller_cannot_lower_intrinsic_risk():
    policy = SecurityPolicy(workspace_root=Path("."), auto_approve_up_to="high")

    class Tool:
        name = "run_command"
        tool_id = "run_command"
        risk_level = "low"
        cfg_auto_accept = False

    assert policy.evaluate_tool_call("run_command", {"command": "ls"}, "low", tool=Tool()) == PolicyDecision.REQUIRE_APPROVAL
