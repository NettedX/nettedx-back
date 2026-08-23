"""交易接口请求与响应模型。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.enums import TransactionStatus
from app.schemas.auth import ETHEREUM_ADDRESS_PATTERN

TRANSACTION_HASH_PATTERN = r"^0x[a-fA-F0-9]{64}$"


class AssetCode(StrEnum):
    USDC = "USDC"
    BOND = "BOND"


class TransactionAssetInput(BaseModel):
    asset: AssetCode
    amount: int = Field(..., gt=0, title="ERC20最小单位正整数")


class CreateTransactionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    receiver_organization_id: int = Field(
        ...,
        gt=0,
        validation_alias="receiverOrganizationId",
        serialization_alias="receiverOrganizationId",
    )
    send: TransactionAssetInput
    receive: TransactionAssetInput

    @model_validator(mode="after")
    def validate_asset_pair(self) -> "CreateTransactionRequest":
        if self.send.asset == self.receive.asset:
            raise ValueError("send and receive assets must be different")
        return self


class OrganizationSummary(BaseModel):
    id: int
    code: str
    name: str


class AssetTypeObject(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    address: str = Field(..., pattern=ETHEREUM_ADDRESS_PATTERN)
    name: str
    symbol: str
    decimals: int = Field(..., ge=0)
    chain_id: int = Field(
        ...,
        gt=0,
        validation_alias="chainId",
        serialization_alias="chainId",
    )


class AssetAmountObject(BaseModel):
    asset: AssetTypeObject
    amount: int = Field(..., gt=0)


class TransactionDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    created_by: OrganizationSummary = Field(
        ...,
        validation_alias="createdBy",
        serialization_alias="createdBy",
    )
    sender_organization: OrganizationSummary = Field(
        ...,
        validation_alias="senderOrganization",
        serialization_alias="senderOrganization",
    )
    send: AssetAmountObject
    receiver_organization: OrganizationSummary = Field(
        ...,
        validation_alias="receiverOrganization",
        serialization_alias="receiverOrganization",
    )
    receive: AssetAmountObject
    status: TransactionStatus
    chain_id: int = Field(
        ...,
        gt=0,
        validation_alias="chainId",
        serialization_alias="chainId",
    )
    window_id: int = Field(
        ...,
        ge=0,
        validation_alias="windowId",
        serialization_alias="windowId",
    )
    submission_hash: str = Field(
        ...,
        pattern=TRANSACTION_HASH_PATTERN,
        validation_alias="submissionHash",
        serialization_alias="submissionHash",
    )
    settlement_hash: str | None = Field(
        default=None,
        pattern=TRANSACTION_HASH_PATTERN,
        validation_alias="settlementHash",
        serialization_alias="settlementHash",
    )
    created_at: int = Field(
        ...,
        gt=0,
        validation_alias="createdAt",
        serialization_alias="createdAt",
    )
    settled_at: int | None = Field(
        default=None,
        gt=0,
        validation_alias="settledAt",
        serialization_alias="settledAt",
    )
    failure_reason: str | None = Field(
        default=None,
        validation_alias="failureReason",
        serialization_alias="failureReason",
    )
