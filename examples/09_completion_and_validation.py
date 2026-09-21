"""Add dropdown help, dynamic suggestions, and input validation.

Run: uv run examples/09_completion_and_validation.py
Type ``deploy `` and use the completion menu.
Try the unique abbreviations: ``dep dev dev-1``.

The provider sees earlier parsed arguments through CompletionContext. A trailing
space advances the menu; the current choice remains selected until then. The
validator receives the converted value and returns an error string to reject it.
Providers supply suggestions, while validators enforce application constraints;
providers should be safe to call repeatedly during completion and dispatch.
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
                help="Deployment environment",
                choices={"development": "Safe sandbox", "production": "Live system"},
            ),
            "server": Argument(
                help="Server to deploy to",
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
