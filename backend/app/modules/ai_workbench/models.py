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
    text,
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


class GenerationJob(TimestampMixin, Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "work_mode IN ('INSTANT', 'BATCH')",
            name="work_mode",
        ),
        CheckConstraint(
            "mode IN ('NORMAL_GENERATION', 'STYLE_REPLICATION')",
            name="mode",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', "
            "'PARTIAL_FAILED', 'FAILED')",
            name="status",
        ),
        CheckConstraint(
            "length(trim(created_by_display_name)) > 0",
            name="creator_name_not_blank",
        ),
        CheckConstraint(
            "length(trim(submission_key)) > 0",
            name="submission_key_not_blank",
        ),
        CheckConstraint(
            "length(submission_fingerprint) = 64",
            name="submission_fingerprint_length",
        ),
        UniqueConstraint(
            "team_id",
            "created_by_user_id",
            "submission_key",
            name="uq_generation_jobs_owner_submission_key",
        ),
        Index(
            "ix_generation_jobs_created_job",
            "created_at",
            "generation_job_id",
        ),
        Index(
            "ix_generation_jobs_team_created_job",
            "team_id",
            "created_at",
            "generation_job_id",
        ),
        Index(
            "ix_generation_jobs_team_creator_created_job",
            "team_id",
            "created_by_user_id",
            "created_at",
            "generation_job_id",
        ),
    )

    generation_job_id: Mapped[UUID] = mapped_column(
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
    created_by_display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    work_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default=text("'PENDING'"),
    )
    submission_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submission_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    items: Mapped[list["GenerationItem"]] = relationship(
        back_populates="job",
        lazy="selectin",
        order_by="GenerationItem.position",
    )


class GenerationItem(TimestampMixin, Base):
    __tablename__ = "generation_items"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint(
            "source_product_position IS NULL OR source_product_position >= 0",
            name="source_product_position_non_negative",
        ),
        CheckConstraint(
            "source_template_group_position IS NULL OR "
            "source_template_group_position >= 0",
            name="source_template_group_position_non_negative",
        ),
        CheckConstraint(
            "source_prompt_template_position IS NULL OR "
            "source_prompt_template_position >= 0",
            name="source_prompt_position_non_negative",
        ),
        CheckConstraint("output_ordinal >= 0", name="output_ordinal_non_negative"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')",
            name="status",
        ),
        CheckConstraint(
            "length(trim(final_prompt)) > 0",
            name="final_prompt_not_blank",
        ),
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
        CheckConstraint("attempt_count > 0", name="attempt_count_positive"),
        CheckConstraint(
            "status <> 'SUCCESS' OR output_asset_id IS NOT NULL",
            name="success_has_output_asset",
        ),
        UniqueConstraint(
            "generation_job_id",
            "position",
            name="uq_generation_items_job_position",
        ),
        UniqueConstraint(
            "output_asset_id",
            name="uq_generation_items_output_asset",
        ),
        Index(
            "ix_generation_items_job_status_position",
            "generation_job_id",
            "status",
            "position",
        ),
        Index(
            "ix_generation_items_source_material_job",
            "source_product_material_group_id",
            "generation_job_id",
        ),
        Index(
            "ix_generation_items_source_template_group",
            "source_template_group_id",
        ),
        Index(
            "ix_generation_items_source_prompt_template",
            "source_prompt_template_id",
        ),
        Index(
            "ix_generation_items_archived_material_group",
            "archived_material_group_id",
        ),
    )

    generation_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    generation_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "generation_jobs.generation_job_id",
            name="fk_generation_items_generation_job",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="PENDING",
        server_default=text("'PENDING'"),
    )
    final_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output_role: Mapped[str] = mapped_column(String(16), nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[str] = mapped_column(String(5), nullable=False)
    source_product_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    source_template_group_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    source_prompt_template_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    output_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_product_material_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "product_material_groups.material_group_id",
            name="fk_generation_items_source_material_group",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    source_template_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "template_groups.template_group_id",
            name="fk_generation_items_source_template_group",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    source_prompt_template_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "prompt_templates.prompt_template_id",
            name="fk_generation_items_source_prompt_template",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    product_name_snapshot: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    template_group_name_snapshot: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    prompt_template_name_snapshot: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    output_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "assets.asset_id",
            name="fk_generation_items_output_asset",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    last_failure_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    last_failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_material_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "product_material_groups.material_group_id",
            name="fk_generation_items_archived_material_group",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    archived_material_group_name_snapshot: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    job: Mapped[GenerationJob] = relationship(back_populates="items")
    input_assets: Mapped[list["GenerationItemAsset"]] = relationship(
        back_populates="item",
        lazy="selectin",
        order_by="(GenerationItemAsset.input_role, GenerationItemAsset.position)",
    )
    output_asset: Mapped[Asset | None] = relationship(
        foreign_keys=[output_asset_id],
        lazy="selectin",
    )


class GenerationItemAsset(Base):
    __tablename__ = "generation_item_assets"
    __table_args__ = (
        CheckConstraint(
            "input_role IN ('PRODUCT_SOURCE', 'STYLE_REFERENCE')",
            name="input_role",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        UniqueConstraint(
            "generation_item_id",
            "input_role",
            "asset_id",
            name="uq_generation_item_assets_item_role_asset",
        ),
        Index(
            "ix_generation_item_assets_asset_item",
            "asset_id",
            "generation_item_id",
        ),
    )

    generation_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "generation_items.generation_item_id",
            name="fk_generation_item_assets_generation_item",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    input_role: Mapped[str] = mapped_column(String(20), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "assets.asset_id",
            name="fk_generation_item_assets_asset",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    item: Mapped[GenerationItem] = relationship(back_populates="input_assets")
    asset: Mapped[Asset] = relationship(lazy="joined")
