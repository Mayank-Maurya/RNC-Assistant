import subprocess
import tempfile
from .skill import Skill

class CodeSkill(Skill):
    """Execute Python code in a local subprocess (sandboxed by timeout)."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "CodeSkill"

    @property
    def description(self) -> str:
        return "Write and execute Python code in an isolated subprocess."

    def get_tools(self) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": "code_execute",
                "description": (
                    "Execute Python code and return stdout/stderr. "
                    f"Runs in a subprocess with a {self.timeout}s timeout."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"}
                    },
                    "required": ["code"]
                }
            }
        }]

    def execute(self, tool_name: str, args: dict) -> str:
        if tool_name != "code_execute":
            raise ValueError(f"Unknown tool: {tool_name}")
        return self._run(args["code"])

    def _run(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            try:
                result = subprocess.run(
                    ["python", f.name],
                    capture_output=True, text=True, timeout=self.timeout
                )
                out = result.stdout
                if result.stderr:
                    out += f"\nSTDERR:\n{result.stderr}"
                return out.strip() or "(no output)"
            except subprocess.TimeoutExpired:
                return f"Error: Timed out after {self.timeout}s."
            finally:
                Path(f.name).unlink(missing_ok=True)
