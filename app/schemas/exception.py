"""定义服务层使用的业务异常。"""

from fastapi import HTTPException


class ServiceException(HTTPException):
    def __init__(self, status_code: int, detail=str) -> None:  # status_code业务码
        super().__init__(status_code=status_code, detail=detail)
