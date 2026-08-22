"""定义登录后银行 Dashboard 四个只读接口的数据模型。"""

from pydantic import BaseModel, Field

from app.schemas.auth import ETHEREUM_ADDRESS_PATTERN


class SettlementWindowForecastData(BaseModel):
    """结算窗口预测。"""

    window_id: int = Field(
        ...,
        ge=0,
        title="当前下一次需要执行结算的窗口编号",
        serialization_alias="windowId",
    )
    settlement_block: int = Field(
        ...,
        ge=0,
        title="预计执行结算的目标区块高度",
        serialization_alias="settlementBlock",
    )
    blocks_remaining: int = Field(
        ...,
        ge=0,
        title="距离目标结算区块的剩余区块数",
        description="到达目标结算区块后为0",
        serialization_alias="blocksRemaining",
    )


class BankNetPositionItem(BaseModel):
    """当前银行对一种金融产品的净结算头寸。"""

    asset: str = Field(
        ...,
        pattern=ETHEREUM_ADDRESS_PATTERN,
        title="ERC20金融产品地址",
    )
    payable_amount: int = Field(
        ...,
        ge=0,
        title="银行应付数量",
        description="ERC20最小单位的原始整数",
        serialization_alias="payableAmount",
    )
    receivable_amount: int = Field(
        ...,
        ge=0,
        title="银行应收数量",
        description="ERC20最小单位的原始整数",
        serialization_alias="receivableAmount",
    )


class SettlementAssetRequirementItem(BaseModel):
    """当前银行必须准备的一种结算资产。"""

    asset: str = Field(
        ...,
        pattern=ETHEREUM_ADDRESS_PATTERN,
        title="ERC20金融产品地址",
        description="银行本轮必须准备的金融产品合约地址",
    )
    required_amount: int = Field(
        ...,
        ge=0,
        title="结算所需数量",
        description="银行本轮结算必须准备的数量，使用ERC20最小单位的原始整数",
        serialization_alias="requiredAmount",
    )


class LiquidityShortfallItem(BaseModel):
    """当前银行对一种结算资产的流动性缺口。"""

    asset: str = Field(
        ...,
        pattern=ETHEREUM_ADDRESS_PATTERN,
        title="ERC20金融产品地址",
        description="存在结算应付义务的金融产品合约地址",
    )
    required_amount: int = Field(
        ...,
        ge=0,
        title="结算所需数量",
        description="银行本轮结算必须准备的数量，使用ERC20最小单位的原始整数",
        serialization_alias="requiredAmount",
    )
    available_balance: int = Field(
        ...,
        ge=0,
        title="银行当前链上余额",
        description="合约查询到的银行当前ERC20余额，使用ERC20最小单位的原始整数",
        serialization_alias="availableBalance",
    )
    borrow_amount: int = Field(
        ...,
        ge=0,
        title="预计借款数量",
        description=(
            "根据当前余额计算的预计借款需求，等于max(required_amount - available_balance, 0)"
        ),
        serialization_alias="borrowAmount",
    )
