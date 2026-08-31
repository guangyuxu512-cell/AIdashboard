from enum import Enum


class DataScope(str, Enum):
    SELF = "self"
    TEAM = "team"
    ALL = "all"
