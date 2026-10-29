"""Host-administration policies, one class per module."""

from __future__ import annotations

from . import destructive, disks, identity, internals, network, privilege, services
from .common import class_pattern, flatten_quotes, strip_wrappers

HOST_CLASSES = (
    (privilege.LABEL, privilege.PATTERN),
    (network.LABEL, network.PATTERN),
    (identity.LABEL, identity.PATTERN),
    (services.LABEL, services.PATTERN),
    (disks.LABEL, disks.PATTERN),
)

__all__ = [
    "HOST_CLASSES",
    "class_pattern",
    "destructive",
    "disks",
    "flatten_quotes",
    "identity",
    "internals",
    "network",
    "privilege",
    "services",
    "strip_wrappers",
]
