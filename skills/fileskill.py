from .skill import Skill
from pathlib import Path

class FileSkill(Skill):
    """Local file operations — read, write, list."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()

    @property
    def name(self) -> str:
        return "FileSkill"

    @property
    def description(self) -> str:
        return "Read, write, and list local files within a sandboxed directory."

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "Read the contents of a text file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative file path"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_write",
                    "description": "Write content to a file (creates parent directories if needed).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative file path"},
                            "content": {"type": "string", "description": "Content to write"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_list",
                    "description": "List files and directories.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Relative directory path", "default": "."}
                        }
                    }
                }
            },
        ]

    def execute(self, tool_name: str, args: dict) -> str:
        if tool_name == "file_read":
            return self._read(args["path"])
        elif tool_name == "file_write":
            return self._write(args["path"], args["content"])
        elif tool_name == "file_list":
            return self._list(args.get("directory", "."))
        raise ValueError(f"Unknown tool: {tool_name}")

    def _read(self, path: str) -> str:
        full = self.base_dir / path
        if not full.resolve().is_relative_to(self.base_dir):
            return "Error: Path escapes sandbox."
        if not full.exists():
            return f"Error: File not found: {path}"
        return full.read_text(encoding="utf-8")

    def _write(self, path: str, content: str) -> str:
        full = self.base_dir / path
        if not full.resolve().is_relative_to(self.base_dir):
            return "Error: Path escapes sandbox."
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"

    def _list(self, directory: str = ".") -> str:
        dir_path = self.base_dir / directory
        if not dir_path.exists():
            return f"Error: Not found: {directory}"
        entries = sorted(dir_path.iterdir())
        lines = [
            f"{'📁' if e.is_dir() else '📄'} {e.name}" for e in entries
            if not e.name.startswith(".")
        ]
        return "\n".join(lines) if lines else "(empty directory)"
