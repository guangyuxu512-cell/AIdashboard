from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.shared.identifiers import generate_id


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="positive_size"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        CheckConstraint(
            "media_type IN ('image', 'video')",
            name="media_type",
        ),
        CheckConstraint(
            "source_type IN ('upload', 'ai_generated', 'imported')",
            name="source_type",
        ),
        CheckConstraint(
            "length(trim(content_type)) > 0",
            name="content_type_not_blank",
        ),
        Index("ix_assets_created_asset", "created_at", "asset_id"),
        Index("ix_assets_original_filename", "original_filename"),
        Index(
            "ix_assets_team_created_asset",
            "team_id",
            "created_at",
            "asset_id",
        ),
        Index(
            "ix_assets_team_creator_created_asset",
            "team_id",
            "created_by_user_id",
            "created_at",
            "asset_id",
        ),
    )

    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    media_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AssetMediaType.IMAGE.value,
        server_default=text("'image'"),
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AssetSourceType.UPLOAD.value,
        server_default=text("'upload'"),
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
