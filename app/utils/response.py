"""提供构造所有api统一成功响应的辅助函数
生成unix秒级时间戳，
并确保成功响应始终使用code、msg、time和data四个字段。
"""

from time import time
from typing import Any, TypeVar

from fastapi.responses import JSONResponse

from app.schemas.response import ApiResponse

DataT = TypeVar("DataT")  # 泛型变量，赋名DataT


def _now_unix() -> int:
    return int(time())


def build_success_response(
    data: DataT,
    msg: str = "ok",
    code: int = 200,
) -> ApiResponse[DataT]:
    return ApiResponse(
        code=code,
        msg=msg,
        time=_now_unix(),
        data=data,
    )


def build_error_response(
    msg: str,
    code: int,  # json响应的业务码
    status_code: int,  # HTTP状态码
    data: dict[str, Any] | list[Any] | None = None,
) -> JSONResponse:
    response_data = {} if data is None else data
    body = build_success_response(
        data=response_data,
        msg=msg,
        code=code,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )
