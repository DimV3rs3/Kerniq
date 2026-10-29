"""Optional Linux account for the Kerniq service. Never required to finish setup.

Default: create a user named kerniq with no superuser rights. If this process
is not root, print the command instead of failing the install.
"""

from __future__ import annotations

import os
import sys


def offer_service_user(name: str = "kerniq", *, create: bool = True, superuser: bool = False) -> None:
    if not create:
        print("No service account was created.")
        return
    if sys.platform != "linux":
        print("A service account is only created on Linux. Skipped.")
        return
    name = "".join(ch for ch in (name or "kerniq") if ch.isalnum() or ch in "-_")[:32] or "kerniq"
    try:
        import pwd

        pwd.getpwnam(name)
        print(f"User {name} already exists. It was left as it is.")
        return
    except KeyError:
        pass
    except Exception:
        pass
    create_cmd = ["useradd", "--system", "--create-home", "--shell", "/usr/sbin/nologin", name]
    shown = " ".join(create_cmd)
    if superuser:
        shown += f" && usermod -aG sudo {name}"
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("This process is not root, so the account was not created.")
        print("Create it with:")
        print("  sudo " + shown)
        return
    import subprocess

    result = subprocess.run(create_cmd, check=False)
    if result.returncode != 0:
        print(f"useradd did not create {name}. You can run it yourself:")
        print("  " + shown)
        return
    print(f"Created system user {name} without a login shell.")
    if superuser:
        grant = subprocess.run(["usermod", "-aG", "sudo", name], check=False)
        if grant.returncode == 0:
            print(f"{name} was added to the sudo group.")
        else:
            print(f"Could not add {name} to sudo. Run: sudo usermod -aG sudo {name}")
    else:
        print(f"{name} has no superuser rights.")
