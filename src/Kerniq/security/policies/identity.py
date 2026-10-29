"""Host-identity commands are denied unless host freedom is on."""

from __future__ import annotations

from .common import class_pattern

LABEL = "host identity"

BODY = (
    r"hostname|hostnamectl|uname|whoami|id|who|users|groups|logname|"
    r"lsb_release|systeminfo|printenv|setx|locate|updatedb|whereis|which|where|getent|"
    r"Get-ComputerInfo|Get-LocalUser|Get-LocalGroup"
)

PATTERN = class_pattern(BODY)
