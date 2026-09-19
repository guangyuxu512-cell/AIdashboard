from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.database import Base
from app.modules.access.models import (
    MembershipModuleAccess,
    Team,
    TeamDeviceAccess,
    TeamMembership,
    TeamModuleAccess,
    TeamShopAccess,
)
from app.modules.audit.models import AuditLog
from app.modules.ai_workbench.models import (
    AiModel,
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.assets.models import Asset
from app.modules.automation_apps.models import (
    AutomationApplicationConfig,
    AutomationParameterPreset,
)
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.devices.models import Device
from app.modules.human_auth.models import HumanSession
from app.modules.notifications.models import NotificationChannel
from app.modules.schedules.models import Schedule, ScheduleRun, ScheduleShop
from app.modules.sessions.models import ShopSession
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.tasks.models import Task, TaskAsset, TaskEvent, TaskShop
from app.modules.users.models import User
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
    WorkerDeviceCredential,
)

_MODELS = (
    AiModel,
    AutomationApplicationConfig,
    AutomationParameterPreset,
    Asset,
    AuditLog,
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
    Device,
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
    HumanSession,
    NotificationChannel,
    Schedule,
    ScheduleRun,
    ScheduleShop,
    PlatformCredential,
    Shop,
    ShopCredentialBinding,
    ShopDeviceBinding,
    ShopSession,
    Task,
    TaskAsset,
    TaskEvent,
    TaskShop,
    Team,
    TeamMembership,
    MembershipModuleAccess,
    TeamModuleAccess,
    TeamDeviceAccess,
    TeamShopAccess,
    User,
    WorkerDeviceCredential,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("BACKEND_DATABASE_URL is required to run migrations")
    return str(database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
