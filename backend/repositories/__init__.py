"""
SAT-SA Repositories Package.
Exports base repository interface, in-memory repository, and PostgreSQL repository.
"""
from backend.repositories.base import (
    AuditEvent,
    BaseSATRepository,
    DatasetMetadata,
    DatasetVersionMetadata,
    ReviewDecisionRecord,
)
from backend.repositories.in_memory_repo import (
    InMemoryRepository,
    SATRepository,
    get_repository,
    set_repository,
)
from backend.repositories.postgres_repo import PostgresRepository

__all__ = [
    "BaseSATRepository",
    "DatasetMetadata",
    "DatasetVersionMetadata",
    "AuditEvent",
    "ReviewDecisionRecord",
    "InMemoryRepository",
    "PostgresRepository",
    "SATRepository",
    "get_repository",
    "set_repository",
]
