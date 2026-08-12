"""定义 SIWE 登录请求及用户认证响应的数据模型。"""

from typing import Literal

from pydantic import BaseModel, Field

ETHEREUM_ADDRESS_PATTERN = r"^0x[a-fA-F0-9]{40}$"
HEX_SIGNATURE_PATTERN = r"^0x[a-fA-F0-9]+$"


class SiweChallengeRequest(BaseModel):
    wallet_address: str = Field(
        ...,
        title="钱包地址",
        description="在浏览器点击钱包连接后获得的Ethereum的钱包地址",
        pattern=ETHEREUM_ADDRESS_PATTERN,
    )
    chain_id: int = Field(
        ...,
        title="区块链网络ID",
        description="EIP-155 Chain ID",
        gt=0,  # greater than 表示该值必须大于0
    )


class SiweChallengeData(BaseModel):
    message: str = Field(
        ...,
        title="SIWE签名消息",
        description="后端生成的完整EIP-4361消息",
        min_length=1,
    )
    expires_at: int = Field(
        ...,
        title="过期时间",
        description="unix秒级时间戳",
        gt=0,
    )


class SiweVerifyRequest(BaseModel):
    message: str = Field(
        ...,
        title="SIWE 原始消息",
        description="钱包实际签署的完整SIWE message",
        min_length=1,
    )
    signature: str = Field(
        ...,
        title="钱包签名",
        description="钱包对完整SIWE message生成的十六进制签名",
        min_length=3,
        pattern=HEX_SIGNATURE_PATTERN,
    )


class UserToken(BaseModel):
    access: str = Field(..., title="访问token", min_length=1)
    refresh: str = Field(..., title="刷新token", min_length=1)


class Organization(BaseModel):
    id: int = Field(..., title="机构 ID")
    code: str = Field(..., title="机构唯一代码", min_length=1)
    name: str = Field(..., title="机构名称", min_length=1)
    wallet_address: str = Field(
        ...,
        title="机构钱包地址",
        pattern=ETHEREUM_ADDRESS_PATTERN,
    )


class UserProfile(BaseModel):
    id: int = Field(..., title="用户ID")
    display_name: str = Field(..., title="用户昵称", min_length=1)
    role: Literal["operator"] = Field(..., title="用户角色")
    organization: Organization
