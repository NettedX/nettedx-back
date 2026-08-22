"""创建并配置FastAPI应用"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import settings
from app.schemas.exception import ServiceException
from app.utils.response import build_error_response

logger = logging.getLogger("uvicorn.error.nettedx")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 调试模式会绕过通用500异常处理器，因此在HTTP中间件中保证统一响应结构
    @app.middleware("http")
    async def unhandled_exception_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(
                "Unhandled exception: method=%s path=%s",
                request.method,
                request.url.path,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return build_error_response(
                msg="internal server error",
                code=500,
                status_code=500,
            )

    # 全局HTTP异常处理器 保留原始http状态码，并生成统一错误响应体
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ):
        detail = exc.detail if isinstance(exc.detail, str) else "request error"

        logger.warning(
            "HTTP error: method=%s path=%s code=%s detail=%s",
            request.method,
            request.url.path,
            exc.status_code,
            detail,
            exc_info=((type(exc), exc, exc.__traceback__) if settings.debug else None),
        )

        return build_error_response(
            msg=detail,
            code=exc.status_code,
            status_code=exc.status_code,
            data={},
        )

    # 业务异常处理器
    @app.exception_handler(ServiceException)
    async def service_exception_handler(
        request: Request,
        exc: ServiceException,
    ):

        if exc.status_code >= 500:
            logger.error(
                "Service error: method=%s path=%s code=%s detail=%s",
                request.method,
                request.url.path,
                exc.status_code,
                exc.detail,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        else:
            logger.warning(
                "Request rejected: method=%s path=%s code=%s detail=%s",
                request.method,
                request.url.path,
                exc.status_code,
                exc.detail,
            )

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

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
