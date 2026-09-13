"""Declare Linux-style short and long named arguments explicitly.

Run: uv run examples/04_named_arguments.py
Try: deploy api
Try: deploy api -e production -r 3
Try: deploy api --environment=production --replicas 3 --verbose

``target`` is positional because it has no ``flags`` configuration. The other
parameters are named arguments and cannot be supplied positionally.
"""

from typing import Literal

from ctui import Argument, CtuiApp, command


class DeployTool(CtuiApp):
    """Combine a positional target with conventional command-line options."""

    @command(
        arguments={
            "environment": Argument(flags=("-e", "--environment")),
            "replicas": Argument(flags=("-r", "--replicas")),
            "verbose": Argument(flags=("-v", "--verbose")),
        }
    )
    def deploy(
        self,
        target: str,
        environment: Literal["development", "production"] = "development",
        replicas: int = 1,
        verbose: bool = False,
    ) -> str:
        """Deploy a target using explicitly named options."""
        detail = " with verbose logging" if verbose else ""
        return f"Deploying {replicas} {target} replica(s) to {environment}{detail}."


if __name__ == "__main__":
    DeployTool().run()
