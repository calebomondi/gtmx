from __future__ import annotations
import uuid

from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UUID, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.connect import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255), index=True, unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048))

    joined: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )

    # Relationships
    workspaces: Mapped[list[Workspace]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    # Metadata
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        index=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # User-owned label, seeded with the product/service name at creation time
    # (product_profile.product_name stays the agent's own understanding).
    name: Mapped[str | None] = mapped_column(String(100))
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    # Dates
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC)
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC)
    )

    # Relationships
    creator: Mapped[User] = relationship(back_populates="workspaces")
    product_profile: Mapped["ProductProfile | None"] = relationship(
        back_populates="workspace",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def product_name(self) -> str | None:
        """Agent-derived product/service name for list responses (requires the
        product_profile relationship to be eagerly loaded)."""
        return self.product_profile.product_name if self.product_profile else None


class ProductProfile(Base):
    __tablename__ = "product_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    product_name: Mapped[str | None] = mapped_column(String(255))
    product_url: Mapped[str | None] = mapped_column(String(2048))
    product_description: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    problem_solved: Mapped[str | None] = mapped_column(Text)
    how_it_works: Mapped[str | None] = mapped_column(Text)

    target_geo: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Final agent-run insights (domain/market/competition/ICP/team + offer
    # snapshot) persisted when the discovery run completes, so workspace tabs
    # can render real data after a refresh.
    insights: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        back_populates="product_profile"
    )
    features: Mapped[list["ProductFeature"]] = relationship(
        back_populates="product_profile",
        cascade="all, delete-orphan",
    )


class ProductFeature(Base):
    __tablename__ = "product_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    differentiator: Mapped[str | None] = mapped_column(Text)

    # Relationships
    product_profile: Mapped["ProductProfile"] = relationship(
        back_populates="features"
    )