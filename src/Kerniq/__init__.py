"""Open Source AI Agent Platform."""

__version__ = "0.1.10"
__build__ = 7


def _quiet_windows() -> None:
    try:
        from Kerniq.sandbox.proc import install_hidden_subprocess

        install_hidden_subprocess()
    except Exception:
        return


_quiet_windows()
