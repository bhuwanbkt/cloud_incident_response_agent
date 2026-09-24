from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.retrieval.runbook_loader import (
    load_runbooks,
)


def test_load_runbooks() -> None:
    settings = get_settings()

    chunks = load_runbooks(
        settings.runbook_directory
    )

    assert len(chunks) > 0

    runbook_names = {
        chunk.runbook_name
        for chunk in chunks
    }

    assert (
        "Database Connection Pool Exhaustion"
        in runbook_names
    )


def test_runbook_sections_are_preserved() -> None:
    settings = get_settings()

    chunks = load_runbooks(
        settings.runbook_directory
    )

    headings = {
        chunk.heading
        for chunk in chunks
        if chunk.runbook_name
        == "Database Connection Pool Exhaustion"
    }

    assert "Symptoms" in headings
    assert "Investigation" in headings
    assert "Remediation" in headings