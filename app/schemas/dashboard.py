"""定义登录后银行 Dashboard 只读接口的数据模型。"""

from pydantic import BaseModel, ConfigDict, Field

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


class AssetTypeObject(BaseModel):
    """Dashboard 展示的一种 ERC20 资产。"""

    model_config = ConfigDict(populate_by_name=True)

    address: str = Field(..., pattern=ETHEREUM_ADDRESS_PATTERN, title="地址")
    name: str = Field(..., min_length=1, title="资产名称")
    symbol: str = Field(..., min_length=1, title="资产单位")
    decimals: int = Field(..., ge=0, le=255, title="小数点")
    chain_id: int = Field(
        ...,
        gt=0,
        title="链id",
        serialization_alias="chainId",
    )


class AssetAmountObject(BaseModel):
    """一种 ERC20 资产及其最小单位整数数量。"""

    asset: AssetTypeObject
    amount: int = Field(..., title="数量", description="ERC20最小单位整数")


class DashboardOverviewData(BaseModel):
    """当前登录银行 Dashboard 所需的五项数据。"""

    model_config = ConfigDict(populate_by_name=True)

    net_amounts: list[AssetAmountObject] = Field(
        ...,
        min_length=2,
        max_length=2,
        title="Netting后净额",
        serialization_alias="netAmounts",
    )
    cumulative_trade_count: int = Field(
        ...,
        ge=0,
        title="累计原始交易次数",
        serialization_alias="cumulativeTradeCount",
    )
    liquidity_buffer_debts: list[AssetAmountObject] = Field(
        ...,
        min_length=2,
        max_length=2,
        title="Liquidity Buffer实际欠款",
        serialization_alias="liquidityBufferDebts",
    )
    cumulative_gross_trade_amounts: list[AssetAmountObject] = Field(
        ...,
        min_length=2,
        max_length=2,
        title="累计原始交易绝对金额",
        serialization_alias="cumulativeGrossTradeAmounts",
    )
    balances: list[AssetAmountObject] = Field(
        ...,
        min_length=2,
        max_length=2,
        title="当前账户余额",
    )
