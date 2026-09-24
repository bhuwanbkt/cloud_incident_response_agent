import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cloud_incident_response_agent.models.runbook import (
    RunbookChunk as DatabaseRunbookChunk,
)
from cloud_incident_response_agent.models.runbook import (
    RunbookDocument,
)
from cloud_incident_response_agent.retrieval.runbook_loader import (
    load_runbook,
)
from cloud_incident_response_agent.services.embeddings import (
    get_embedding_service,
)


@dataclass(frozen=True)
class RunbookSyncResult:
    created_documents: int
    updated_documents: int
    unchanged_documents: int
    deleted_documents: int
    stored_chunks: int


def create_hash(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def create_embedding_text(
    runbook_name: str,
    heading: str,
    content: str,
) -> str:
    return (
        f"Runbook: {runbook_name}\n"
        f"Section: {heading}\n"
        f"{content}"
    )


def sync_runbooks(
    database: Session,
    runbook_directory: Path,
) -> RunbookSyncResult:
    """
    Synchronize Markdown runbooks with PostgreSQL.

    New files are inserted.
    Changed files are reprocessed.
    Unchanged files are skipped.
    Deleted files are removed from the database.
    """
    resolved_directory = (
        runbook_directory.resolve()
    )

    if not resolved_directory.exists():
        raise FileNotFoundError(
            "Runbook directory does not exist: "
            f"{resolved_directory}"
        )

    markdown_files = sorted(
        resolved_directory.glob("*.md")
    )

    existing_documents = {
        document.file_name: document
        for document in database.scalars(
            select(RunbookDocument)
        ).all()
    }

    current_file_names = {
        file_path.name
        for file_path in markdown_files
    }

    embedding_service = (
        get_embedding_service()
    )

    created_documents = 0
    updated_documents = 0
    unchanged_documents = 0
    deleted_documents = 0
    stored_chunks = 0

    try:
        for file_path in markdown_files:
            file_text = file_path.read_text(
                encoding="utf-8"
            )

            file_hash = create_hash(file_text)

            existing_document = (
                existing_documents.get(
                    file_path.name
                )
            )

            if (
                existing_document is not None
                and existing_document.file_hash
                == file_hash
            ):
                unchanged_documents += 1
                continue

            loaded_chunks = load_runbook(
                file_path
            )

            if loaded_chunks:
                runbook_name = (
                    loaded_chunks[0].runbook_name
                )
            else:
                runbook_name = (
                    file_path.stem.replace(
                        "_",
                        " ",
                    ).replace(
                        "-",
                        " ",
                    ).title()
                )

            embedding_texts = [
                create_embedding_text(
                    runbook_name=(
                        chunk.runbook_name
                    ),
                    heading=chunk.heading,
                    content=chunk.content,
                )
                for chunk in loaded_chunks
            ]

            embeddings = (
                embedding_service.embed_texts(
                    embedding_texts
                )
            )

            if existing_document is None:
                document = RunbookDocument(
                    runbook_name=runbook_name,
                    file_name=file_path.name,
                    file_path=str(file_path),
                    file_hash=file_hash,
                )

                database.add(document)
                database.flush()

                created_documents += 1
            else:
                document = existing_document

                document.runbook_name = (
                    runbook_name
                )
                document.file_path = str(
                    file_path
                )
                document.file_hash = file_hash

                database.execute(
                    delete(DatabaseRunbookChunk)
                    .where(
                        DatabaseRunbookChunk
                        .document_id
                        == document.id
                    )
                )

                database.flush()

                updated_documents += 1

            for chunk_index, (
                chunk,
                embedding,
            ) in enumerate(
                zip(
                    loaded_chunks,
                    embeddings,
                    strict=True,
                )
            ):
                embedding_text = (
                    embedding_texts[chunk_index]
                )

                database.add(
                    DatabaseRunbookChunk(
                        document_id=document.id,
                        chunk_index=chunk_index,
                        heading=chunk.heading,
                        content=chunk.content,
                        content_hash=create_hash(
                            embedding_text
                        ),
                        embedding=embedding,
                    )
                )

                stored_chunks += 1

        for file_name, document in (
            existing_documents.items()
        ):
            if file_name not in current_file_names:
                database.delete(document)
                deleted_documents += 1

        database.commit()

    except Exception:
        database.rollback()
        raise

    return RunbookSyncResult(
        created_documents=created_documents,
        updated_documents=updated_documents,
        unchanged_documents=(
            unchanged_documents
        ),
        deleted_documents=deleted_documents,
        stored_chunks=stored_chunks,
    )