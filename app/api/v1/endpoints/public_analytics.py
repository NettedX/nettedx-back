"""提供首页公开分析指标的查询接口。"""

from fastapi import APIRouter

from app.schemas.public_analytics import PublicAnalyticsData
from app.schemas.response import ApiResponse
from app.services.public_analytics import get_public_analytics
from app.utils.response import build_success_response

router = APIRouter(prefix="/public", tags=["public"])


@router.get(
    "/analytics",
    response_model=ApiResponse[PublicAnalyticsData],
)
async def get_public_analytics_metrics() -> ApiResponse[PublicAnalyticsData]:
    data = await get_public_analytics()
    return build_success_response(data=data)
