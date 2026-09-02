from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.modules.assets.models import Asset
from app.shared.identifiers import generate_id


class TemplateGroup(TimestampMixin, Base):
    __tablename__ = "template_groups"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "mode IN ('NORMAL_GENERATION', 'STYLE_REPLICATION')",
            name="mode",
        ),
        Index(
            "ix_template_groups_created_group",
            "created_at",
            "template_group_id",
        ),
        Index(
            "ix_template_groups_team_created_group",
            "team_id",
            "created_at",
            "template_group_id",
        ),
        Index(
            "ix_template_groups_team_creator_created_group",
            "team_id",
            "created_by_user_id",
            "created_at",
            "template_group_id",
        ),
    )

    template_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    prompt_templates: Mapped[list["PromptTemplate"]] = relationship(
        back_populates="template_group",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PromptTemplate.sort_order",
    )


class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "output_role IN ('MAIN_IMAGE', 'DETAIL_IMAGE')",
            name="output_role",
        ),
        CheckConstraint(
            "output_format IN ('SINGLE', 'COLLAGE_2X2')",
            name="output_format",
        ),
        CheckConstraint(
            "size IN ('1:1', '3:4', '4:3', '16:9')",
            name="size",
        ),
        CheckConstraint("count BETWEEN 1 AND 8", name="count"),
        CheckConstraint("jsonb_typeof(variables) = 'array'", name="variables_array"),
        CheckConstraint("length(trim(prompt)) > 0", name="prompt_not_blank"),
        CheckConstraint("sort_order > 0", name="sort_order_positive"),
        UniqueConstraint(
            "template_group_id",
            "sort_order",
            name="uq_prompt_templates_group_sort_order",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    prompt_template_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    template_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("template_groups.template_group_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    output_role: Mapped[str] = mapped_column(String(16), nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[str] = mapped_column(String(5), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    template_group: Mapped[TemplateGroup] = relationship(
        back_populates="prompt_templates",
    )


class ProductMaterialGroup(TimestampMixin, Base):
    __tablename__ = "product_material_groups"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        Index(
            "ix_product_material_groups_created_group",
            "created_at",
            "material_group_id",
        ),
        Index(
            "ix_product_material_groups_team_created_group",
            "team_id",
            "created_at",
            "material_group_id",
        ),
        Index(
            "ix_product_material_groups_team_creator_created_group",
            "team_id",
            "created_by_user_id",
            "created_at",
            "material_group_id",
        ),
    )

    material_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    normal_generation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    style_replication_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    asset_links: Mapped[list["MaterialGroupAsset"]] = relationship(
        back_populates="material_group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    template_bindings: Mapped[list["MaterialGroupTemplateBinding"]] = relationship(
        back_populates="material_group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MaterialGroupAsset(Base):
    __tablename__ = "material_group_assets"
    __table_args__ = (
        CheckConstraint(
            "role IN ('PRODUCT_SOURCE', 'STYLE_REFERENCE', 'AI_OUTPUT')",
            name="role",
        ),
        Index(
            "ix_material_group_assets_asset_group",
            "asset_id",
            "material_group_id",
        ),
    )

    material_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "product_material_groups.material_group_id",
            name="fk_material_group_assets_material_group",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "assets.asset_id",
            name="fk_material_group_assets_asset",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    material_group: Mapped[ProductMaterialGroup] = relationship(
        back_populates="asset_links",
    )
    asset: Mapped[Asset] = relationship(lazy="joined")


class MaterialGroupTemplateBinding(Base):
    __tablename__ = "material_group_template_bindings"
    __table_args__ = (
        CheckConstraint(
            "generation_mode IN ('NORMAL_GENERATION', 'STYLE_REPLICATION')",
            name="generation_mode",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        UniqueConstraint(
            "material_group_id",
            "generation_mode",
            "position",
            name="uq_material_group_template_bindings_group_mode_position",
        ),
        Index(
            "ix_material_group_template_bindings_template_group",
            "template_group_id",
            "material_group_id",
        ),
    )

    material_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "product_material_groups.material_group_id",
            name="fk_material_template_bindings_material_group",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    template_group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "template_groups.template_group_id",
            name="fk_material_template_bindings_template_group",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    generation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    material_group: Mapped[ProductMaterialGroup] = relationship(
        back_populates="template_bindings",
    )
