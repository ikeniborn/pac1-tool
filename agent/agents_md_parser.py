def parse_agents_md(content: str) -> dict[str, list[str]]:
    """Parse AGENTS.MD into {section_name: [lines]} for each ## section."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in content.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower().replace(" ", "_")
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections
