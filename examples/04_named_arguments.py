"""Declare Linux-style short and long named arguments explicitly.

Run: uv run examples/04_named_arguments.py
Try: deploy api
Try: deploy api -e production -r 3
Try: deploy api --environment=production --replicas 3 --verbose

``target`` is positional because it has no ``flags`` configuration. The other
parameters are named arguments and cannot be supplied positionally.

``Argument(help=...)`` explains an option in the suggestion menu and in
``help deploy``. For free-form values, it accompanies the type hint. Adding
help to ``target`` does not make it named: only ``flags`` does that.
A ``choices`` mapping supplies a separate description for each suggested value.

Try typing ``deploy `` to see target help, ``deploy api --`` to explore options,
and ``deploy api -e `` to see descriptions for the environment choices.
"""

from typing import Literal

from ctui import Argument, CtuiApp, command


class DeployTool(CtuiApp):
    """Combine a positional target with conventional command-line options."""

    @command(
        arguments={
            "target": Argument(help="Service to deploy, such as api or worker"),
            "environment": Argument(
                flags=("-e", "--environment"),
                help="Deployment environment (default: development)",
                choices={
                    "development": "Testing environment for development work",
                    "production": "Live environment serving users",
                },
            ),
            "replicas": Argument(
                flags=("-r", "--replicas"),
                help="Number of service instances to deploy (default: 1)",
            ),
            "verbose": Argument(
                flags=("-v", "--verbose"),
                help="Enable verbose logging",
            ),
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
