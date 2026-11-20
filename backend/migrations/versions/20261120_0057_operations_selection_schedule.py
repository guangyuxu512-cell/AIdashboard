"""Schedule independent operations strategies without reviving central selection."""
from alembic import op
import sqlalchemy as sa

revision = '20261120_0057'
down_revision = '20261116_0056'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('operations_selection_schedules',
        sa.Column('schedule_id', sa.Uuid(), primary_key=True),
        sa.Column('team_id', sa.Uuid(), sa.ForeignKey('teams.team_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_by_user_id', sa.Uuid(), sa.ForeignKey('users.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('strategy_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('local_time', sa.Time(timezone=False)),
        sa.Column('interval_hours', sa.Integer()),
        sa.Column('next_run_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('team_id', 'strategy_id', name='uq_ops_schedule_team_strategy'),
        sa.CheckConstraint("kind IN ('daily', 'hourly')", name=op.f('ck_operations_selection_schedules_kind')),
        sa.CheckConstraint("(kind = 'daily' AND local_time IS NOT NULL AND interval_hours IS NULL) OR "
                           "(kind = 'hourly' AND local_time IS NULL AND interval_hours BETWEEN 1 AND 24)",
                           name=op.f('ck_operations_selection_schedules_rule')))
    op.create_index('ix_ops_schedule_due', 'operations_selection_schedules', ['next_run_at'],
                    postgresql_where=sa.text('enabled IS TRUE AND next_run_at IS NOT NULL'))
    op.create_table('operations_selection_schedule_runs',
        sa.Column('run_id', sa.Uuid(), primary_key=True),
        sa.Column('schedule_id', sa.Uuid(), sa.ForeignKey('operations_selection_schedules.schedule_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('submission_key', sa.Uuid(), nullable=False),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('operations_run_id', sa.Uuid()),
        sa.Column('error_code', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('schedule_id', 'scheduled_for', name='uq_ops_schedule_occurrence'),
        sa.UniqueConstraint('submission_key', name='uq_ops_schedule_submission'),
        sa.CheckConstraint("state IN ('pending', 'sent', 'failed', 'cancelled')",
                           name=op.f('ck_operations_selection_schedule_runs_state')))
    op.create_index('ix_ops_schedule_pending', 'operations_selection_schedule_runs', ['next_attempt_at'],
                    postgresql_where=sa.text("state = 'pending'"))


def downgrade():
    bind = op.get_bind()
    for table in ('operations_selection_schedule_runs', 'operations_selection_schedules'):
        if bind.execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one():
            raise RuntimeError('Operations schedules contain records; preserve data and disable execution instead')
    op.drop_index('ix_ops_schedule_pending', table_name='operations_selection_schedule_runs')
    op.drop_table('operations_selection_schedule_runs')
    op.drop_index('ix_ops_schedule_due', table_name='operations_selection_schedules')
    op.drop_table('operations_selection_schedules')
