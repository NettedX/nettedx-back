"""定义数据库模型使用的状态枚举。"""

from enum import StrEnum


# 机构当前的可用状态
class OrganizationStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


# 用户当前的可用状态
class UserStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
