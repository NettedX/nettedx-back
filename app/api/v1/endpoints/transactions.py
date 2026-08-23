"""交易创建、查询与验证接口。"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.dependencies.auth import AccessTokenPayload
from app.db.session import DbSession
from app.schemas.response import ApiResponse
from app.schemas.transactions import (
    TRANSACTION_HASH_PATTERN,
    CreateTransactionRequest,
    OrganizationSummary,
    TransactionDetail,
)
from app.services.transactions import (
    create_transaction,
    get_tradeable_organizations,
    get_transaction,
    list_transactions,
    verify_transaction,
)
from app.utils.response import build_success_response

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/send", response_model=ApiResponse[TransactionDetail])
async def send_transaction(
    request: CreateTransactionRequest,
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[TransactionDetail]:
    data = await create_transaction(db=db, uid=token_payload["uid"], request=request)
    return build_success_response(data=data)


@router.get("", response_model=ApiResponse[list[TransactionDetail]])
async def read_transactions(
    token_payload: AccessTokenPayload,
    db: DbSession,
    is_related: Annotated[bool, Query(alias="isRelated")] = False,
) -> ApiResponse[list[TransactionDetail]]:
    data = await list_transactions(
        db=db,
        uid=token_payload["uid"],
        is_related=is_related,
    )
    return build_success_response(data=data)


@router.get("/verify", response_model=ApiResponse[TransactionDetail | None])
async def verify_transaction_hash(
    db: DbSession,
    submission_hash: Annotated[
        str,
        Query(alias="submissionHash", pattern=TRANSACTION_HASH_PATTERN),
    ],
) -> ApiResponse[TransactionDetail | None]:
    data = await verify_transaction(db=db, submission_hash=submission_hash)
    return build_success_response(data=data)


@router.get("/organizations", response_model=ApiResponse[list[OrganizationSummary]])
async def read_tradeable_organizations(
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[list[OrganizationSummary]]:
    data = await get_tradeable_organizations(db=db, uid=token_payload["uid"])
    return build_success_response(data=data)


@router.get("/{transactionId}", response_model=ApiResponse[TransactionDetail])
async def read_transaction(
    transactionId: Annotated[int, Path(gt=0)],
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[TransactionDetail]:
    data = await get_transaction(
        db=db,
        uid=token_payload["uid"],
        transaction_id=transactionId,
    )
    return build_success_response(data=data)
