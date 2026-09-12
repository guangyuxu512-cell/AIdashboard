"""persist one parameter schema snapshot for every automation preset.

Revision ID: 20260912_0036
Revises: 20260912_0035
Create Date: 2026-09-12

The application-level schema remains the initial template for a *new* preset.
Existing preset values are interpreted only through the copied snapshot so a
later application-template edit cannot silently alter Task or Schedule input.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260912_0036"
down_revision: str | None = "20260912_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "automation_parameter_presets",
        sa.Column(
            "input_schema_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    # A legacy preset has no independent schema.  Copy only fields that have
    # evidence in its saved public/store values.  Unknown keys stay in their
    # original JSONB values but deliberately do not receive invented schema,
    # type, default, or label; the service reports them as invalid diagnostics.
    op.execute(
        sa.text(
            """
            UPDATE automation_parameter_presets AS preset
            SET input_schema_snapshot = jsonb_build_object(
                'fields',
                COALESCE(
                    (
                        SELECT jsonb_agg(field.value ORDER BY field.ordinality)
                        FROM automation_application_configs AS config
                        CROSS JOIN LATERAL jsonb_array_elements(
                            config.input_schema -> 'fields'
                        ) WITH ORDINALITY AS field(value, ordinality)
                        WHERE config.provider_code = 'yingdao'
                          AND config.app_id = preset.app_id
                          AND field.value ->> 'name' IN (
                              SELECT public_key.name
                              FROM jsonb_object_keys(
                                  preset.common_parameters
                              ) AS public_key(name)
                              UNION
                              SELECT override_key.name
                              FROM jsonb_each(preset.shop_overrides) AS shop(
                                  shop_id,
                                  override_values
                              )
                              CROSS JOIN LATERAL jsonb_object_keys(
                                  shop.override_values
                              ) AS override_key(name)
                          )
                    ),
                    '[]'::jsonb
                )
            )
            """,
        ),
    )
    op.alter_column("automation_parameter_presets", "input_schema_snapshot", nullable=False)
    op.create_check_constraint(
        "ck_automation_parameter_presets_input_schema_snapshot_object",
        "automation_parameter_presets",
        "jsonb_typeof(input_schema_snapshot) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_automation_parameter_presets_input_schema_snapshot_object",
        "automation_parameter_presets",
        type_="check",
    )
    op.drop_column("automation_parameter_presets", "input_schema_snapshot")
