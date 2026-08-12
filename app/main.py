"""创建并配置FastAPI应用"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.router import api_router
from app.core.config import settings
from app.schemas.exception import ServiceException
from app.utils.response import build_error_response


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )

    # 全局HTTP异常处理器 保留原始http状态码，并生成统一错误响应体
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _: Request,  # ???
        exc: HTTPException,
    ):
        detail = exc.detail if isinstance(exc.detail, str) else "request error"
        return build_error_response(
            msg=detail,
            code=exc.status_code,
            status_code=exc.status_code,
            data={},
        )

    # 业务异常处理器
    @app.exception_handler(ServiceException)
    async def service_exception_handler(
        _: Request,
        exc: ServiceException,
    ):
        return build_error_response(
            msg=exc.detail,
            code=exc.status_code,
            status_code=200,  # 固定返回200，错误原因通过code和msg体现
            data={},
        )

    # 路由不存在，404异常处理器
    @app.exception_handler(404)
    async def not_found_exception_handler(
        request: Request,
        _: HTTPException,
    ):
        return build_error_response(
            msg="endpoint not found",
            code=404,
            status_code=404,
            data={"url": str(request.url)},  # 在data中记录请求地址
        )

    # 422错误处理器（参数校验失败）
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request,
        exc: RequestValidationError,
    ):
        errors = [error.get("msg", "validation error") for error in exc.errors()]  # 提取各字段信息
        return build_error_response(
            msg="validation error",
            code=422,
            status_code=422,
            data=errors,  # 保存错误信息
        )

    # 500错误处理器
    @app.exception_handler(Exception)
    async def generic_exception_handler(
        _: Request,
        exc: Exception,
    ):
        return build_error_response(
            msg="internal server error",
            code=500,
            status_code=500,
            data={"detail": str(exc)},
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
