"""定义首页公开分析接口返回的4项业务数据模型。"""

from pydantic import BaseModel, Field


class PublicAnalyticsData(BaseModel):
    total_settlement_amount: int = Field(
        ...,
        ge=0,
        title="总清算量",
        description="现金代币完整单位的整数金额",
    )
    total_trade_count: int = Field(
        ...,
        ge=0,
        title="交易总笔数",
        description="当前结算窗口内提交的原始交易数量",
    )
    liquidity_saved: int = Field(
        ...,
        ge=0,
        title="节省流动性",
        description="现金代币完整单位的整数金额",
    )
    obligation_reduction: int = Field(
        ...,
        ge=0,
        le=100,
        title="义务减少比例",
        description="0至100之间的整数百分比",
    )
