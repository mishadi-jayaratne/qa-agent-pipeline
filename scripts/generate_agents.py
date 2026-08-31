#!/usr/bin/env python3
"""
Generates agent AND command files for Claude Code from shared source files:

  Agents:
    - config/agents.yaml         (metadata: id, description, tools)
    - prompts/<id>.md            (system prompt body - single source of truth)
    -> .claude/agents/<id>.md

  Commands:
    - config/commands.yaml       (metadata: id, description, argument_hint)
    - prompts/commands/<id>.md   (command template body - single source of truth)
    -> .claude/commands/<id>.md

Run this after adding/editing anything in prompts/, config/agents.yaml, or config/commands.yaml:
    python3 scripts/generate_agents.py

Generated files ARE committed to the repo, so cloning it works immediately
without running this script. Only re-run it when you change a source file.
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml --break-system-packages")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "agents.yaml"
COMMANDS_CONFIG = ROOT / "config" / "commands.yaml"
PROMPTS_DIR = ROOT / "prompts"
COMMAND_PROMPTS_DIR = ROOT / "prompts" / "commands"
CLAUDE_DIR = ROOT / ".claude" / "agents"
CLAUDE_CMD_DIR = ROOT / ".claude" / "commands"

# All tool capability keys this repo knows about, and how each maps to each
# tool's frontmatter format. Keep this list in sync with what prompts actually need.
CLAUDE_TOOL_NAMES = {
    "read": "Read",
    "grep": "Grep",
    "glob": "Glob",
    "bash": "Bash",
    "write": "Write",
    "edit": "Edit",
}


def load_config():
    with open(CONFIG) as f:
        data = yaml.safe_load(f)
    return data["agents"]


def read_prompt_body(agent_id: str) -> str:
    path = PROMPTS_DIR / f"{agent_id}.md"
    if not path.exists():
        sys.exit(f"Missing prompt file: {path}")
    return path.read_text().strip() + "\n"


def clean_description(desc: str) -> str:
    # YAML block scalars (">-") fold newlines to spaces; collapse any extra whitespace.
    return " ".join(desc.split())


def write_claude_agent(agent: dict, body: str):
    tools = ", ".join(CLAUDE_TOOL_NAMES[t] for t in agent["tools"])
    desc = clean_description(agent["description"])
    frontmatter = (
        "---\n"
        f"name: {agent['id']}\n"
        f"description: {desc}\n"
        f"tools: {tools}\n"
        "---\n\n"
    )
    out_path = CLAUDE_DIR / f"{agent['id']}.md"
    out_path.write_text(frontmatter + body)
    print(f"  wrote {out_path.relative_to(ROOT)}")


def load_commands_config():
    if not COMMANDS_CONFIG.exists():
        return []
    with open(COMMANDS_CONFIG) as f:
        data = yaml.safe_load(f)
    return (data or {}).get("commands", [])


def read_command_body(cmd_id: str) -> str:
    path = COMMAND_PROMPTS_DIR / f"{cmd_id}.md"
    if not path.exists():
        sys.exit(f"Missing command prompt file: {path}")
    return path.read_text().strip() + "\n"


def write_claude_command(cmd: dict, body: str):
    desc = clean_description(cmd["description"])
    lines = ["---", f"description: {desc}"]
    if cmd.get("argument_hint"):
        hint = cmd["argument_hint"].replace('"', '\\"')
        lines.append(f'argument-hint: "{hint}"')
    lines.append("---")
    frontmatter = "\n".join(lines) + "\n\n"
    out_path = CLAUDE_CMD_DIR / f"{cmd['id']}.md"
    out_path.write_text(frontmatter + body)
    print(f"  wrote {out_path.relative_to(ROOT)}")


def main():
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    CLAUDE_CMD_DIR.mkdir(parents=True, exist_ok=True)

    agents = load_config()
    seen_ids = set()
    print(f"Generating {len(agents)} agents for Claude Code...\n")
    for agent in agents:
        if agent["id"] in seen_ids:
            sys.exit(f"Duplicate agent id in config/agents.yaml: {agent['id']}")
        seen_ids.add(agent["id"])

        unknown = set(agent["tools"]) - set(CLAUDE_TOOL_NAMES)
        if unknown:
            sys.exit(f"{agent['id']}: unknown tool(s) {unknown} in config/agents.yaml")

        body = read_prompt_body(agent["id"])
        write_claude_agent(agent, body)

    commands = load_commands_config()
    seen_cmd_ids = set()
    print(f"\nGenerating {len(commands)} command(s) for Claude Code...\n")
    for cmd in commands:
        if cmd["id"] in seen_cmd_ids:
            sys.exit(f"Duplicate command id in config/commands.yaml: {cmd['id']}")
        seen_cmd_ids.add(cmd["id"])

        body = read_command_body(cmd["id"])
        write_claude_command(cmd, body)

    print("\nDone. Review the diffs, then commit .claude/{agents,commands}.")


if __name__ == "__main__":
    main()
