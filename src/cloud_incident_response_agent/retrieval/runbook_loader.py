from pathlib import Path

from cloud_incident_response_agent.retrieval.schemas import (
    RunbookChunk,
)


def clean_heading(line: str) -> str:
    return line.lstrip("#").strip()


def load_runbook(
    file_path: Path,
) -> list[RunbookChunk]:
    text = file_path.read_text(
        encoding="utf-8"
    )

    lines = text.splitlines()

    runbook_name = file_path.stem.replace(
        "_",
        " ",
    ).title()

    current_heading = "Overview"
    current_lines: list[str] = []
    chunks: list[RunbookChunk] = []

    def save_current_section() -> None:
        content = "\n".join(
            current_lines
        ).strip()

        if not content:
            return

        chunks.append(
            RunbookChunk(
                runbook_name=runbook_name,
                file_name=file_path.name,
                heading=current_heading,
                content=content,
            )
        )

    for line in lines:
        stripped_line = line.strip()

        if stripped_line.startswith("#"):
            save_current_section()

            current_lines.clear()

            heading = clean_heading(
                stripped_line
            )

            if stripped_line.startswith("# "):
                runbook_name = heading
                current_heading = "Overview"
            else:
                current_heading = heading

            continue

        current_lines.append(line)

    save_current_section()

    return chunks


def load_runbooks(
    runbook_directory: Path,
) -> list[RunbookChunk]:
    if not runbook_directory.exists():
        return []

    chunks: list[RunbookChunk] = []

    for file_path in sorted(
        runbook_directory.glob("*.md")
    ):
        chunks.extend(
            load_runbook(file_path)
        )

    return chunks