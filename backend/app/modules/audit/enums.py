from enum import Enum


class AuditAction(str, Enum):
    CREATE_MEMBER = "access_management.create_member"
    UPDATE_MEMBER = "access_management.update_member"
    RESET_MEMBER_PASSWORD = "access_management.reset_member_password"
    CREATE_MEMBERSHIP = "access_management.create_membership"
    UPDATE_MEMBERSHIP = "access_management.update_membership"
    CREATE_TEAM = "access_management.create_team"
    UPDATE_TEAM = "access_management.update_team"
    MOVE_MEMBER_TEAM = "access_management.move_member_team"
    REMOVE_MEMBER_FROM_TEAM = "access_management.remove_member_from_team"
    ARCHIVE_TEAM = "access_management.archive_team"
    DELETE_TEAM = "access_management.delete_team"
    UPDATE_TEAM_AUTHORIZATION = "access_management.update_team_authorization"
    DESIGNATE_SUPER_ACCOUNT = "access_management.designate_super_account"


class AuditTargetType(str, Enum):
    USER = "user"
    MEMBERSHIP = "membership"
    TEAM = "team"
