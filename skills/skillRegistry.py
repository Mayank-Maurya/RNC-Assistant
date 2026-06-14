from .skill import Skill

class SkillRegistry:
    """Registry that manages skills and dispatches tool calls."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._tool_to_skill: dict[str, str] = {}

    def register(self, skill: Skill):
        """Register a skill and index its tools."""
        self._skills[skill.name] = skill
        for tool in skill.get_tools():
            tool_name = tool["function"]["name"]
            self._tool_to_skill[tool_name] = skill.name

    def get_all_tools(self) -> list[dict]:
        """Return all tool schemas from all registered skills."""
        tools = []
        for skill in self._skills.values():
            tools.extend(skill.get_tools())
        return tools

    def execute_tool(self, tool_name: str, args: dict) -> str:
        """Route a tool call to the correct skill."""
        skill_name = self._tool_to_skill.get(tool_name)
        print("skill name: ", skill_name, " tool name: ",tool_name)
        if not skill_name:
            return f"Error: Unknown tool '{tool_name}'"
        return self._skills[skill_name].execute(tool_name, args)

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def __repr__(self) -> str:
        skills = ", ".join(self._skills.keys())
        tools = ", ".join(self._tool_to_skill.keys())
        return f"SkillRegistry(skills=[{skills}], tools=[{tools}])"
