import json
from dataclasses import asdict

from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.database import (
    SessionLocal,
    initialize_database,
)
from cloud_incident_response_agent.services.runbook_sync import (
    sync_runbooks,
)


def main() -> None:
    settings = get_settings()

    initialize_database()

    with SessionLocal() as database:
        result = sync_runbooks(
            database=database,
            runbook_directory=(
                settings.runbook_directory
            ),
        )

    print(
        json.dumps(
            asdict(result),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()