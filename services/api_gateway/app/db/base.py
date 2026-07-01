"""
SQLAlchemy declarative base and common mixins.

Provides base class for all ORM models with common fields
like UUID primary keys, timestamps, and soft delete support.
"""

import uuid
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Configures naming conventions for constraints and indexes
    to ensure consistent schema generation.
    """

    pass


class UUIDMixin:
    """
    Mixin adding a UUID primary key column.

    Uses PostgreSQL's native UUID type with server-side generation
    via gen_random_uuid() for optimal performance.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        doc="Unique identifier for the record",
    )


class TimestampMixin:
    """
    Mixin adding created_at and updated_at timestamps.

    Both timestamps use timezone-aware UTC datetime.
    updated_at is automatically updated on row modification.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Record last update timestamp (UTC)",
    )


class SoftDeleteMixin:
    """
    Mixin adding soft delete capability.

    Deleted records are marked with deleted_at timestamp instead
    of being physically removed from the database.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Soft delete timestamp (UTC); null if not deleted",
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Base model combining UUID and timestamps.

    All application models should inherit from this class
    to ensure consistent primary keys and audit fields.
    """

    __abstract__ = True


class BaseModelSoftDelete(BaseModel, SoftDeleteMixin):
    """
    Base model with soft delete support.

    Inherit from this for models that require soft deletion.
    """

    __abstract__ = True