from enum import Enum


class AuditAction(str, Enum):
    CREATE_MEMBER = "access_management.create_member"
    UPDATE_MEMBER = "access_management.update_member"
    RESET_MEMBER_PASSWORD = "access_management.reset_member_password"
    CREATE_MEMBERSHIP = "access_management.create_membership"
    UPDATE_MEMBERSHIP = "access_management.update_membership"
    CREATE_TEAM = "access_management.create_team"
    UPDATE_TEAM = "access_management.update_team"


class AuditTargetType(str, Enum):
    USER = "user"
    MEMBERSHIP = "membership"
    TEAM = "team"
