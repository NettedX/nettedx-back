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


class TransactionStatus(StrEnum):
    """交易记录在 Demo 中使用的三个状态。"""

    SUBMITTED = "submitted"
    SETTLED = "settled"
    FAILED = "failed"
