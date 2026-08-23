"""Add dropdown help, dynamic suggestions, and input validation.

Run: uv run examples/04_completion_and_validation.py
Type ``deploy `` and use the completion menu.
"""

from ctui import Argument, CtuiApp, command


def server_names(context):
    """Suggest servers after considering earlier arguments."""
    prefix = "dev" if context.arguments.get("environment") == "development" else "web"
    return [f"{prefix}-1", f"{prefix}-2"]


class DeployTool(CtuiApp):
    """Demonstrate contextual completion that rejects invalid values."""

    @command(
        arguments={
            "environment": Argument(
                choices={"development": "Safe sandbox", "production": "Live system"}
            ),
            "server": Argument(
                completer=server_names,
                validator=lambda value: value.endswith(("-1", "-2"))
                or "Server names must end in -1 or -2",
            ),
        }
    )
    def deploy(self, environment: str, server: str) -> str:
        """Deploy to one server."""
        return f"Deploying to {server} in {environment}"


if __name__ == "__main__":
    DeployTool().run()
