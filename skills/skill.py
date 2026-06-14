from abc import ABC, abstractmethod

class Skill(ABC):
    """Base class for RnC Skill."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable skill name."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """what the skill does - shown in LLM."""
        ...

    @abstractmethod
    def get_tools(self) -> list[dict]:
        """Return OpenAI-compatible tool schema."""
        ...
    
    @abstractmethod
    def execute(self, tool_name: str, args: dict) -> any:
        """Execute a tool by name with givem arguments."""
        ...

    