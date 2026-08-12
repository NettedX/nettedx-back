"""定义所有api的统一响应数据模型，
所有业务api使用code、msg、time和data四个字段返回结果。
ApiResponse通过泛型支持不同api使用不同类型的业务数据data
比如刷新token接口可用ApiResponse[UserToken]
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")  # TypeVar是类型变量，定义一个泛型类型参数，名字叫DataT


# Generic[DataT] 表示 data 的类型可以根据接口变化
class ApiResponse(BaseModel, Generic[DataT]):
    code: int = Field(..., title="响应码")  # Field(...)表示该字段必填
    msg: str = Field(..., title="消息")
    time: int = Field(..., title="时间", description="unix秒级时间戳")
    data: DataT = Field(..., title="业务数据")
