from datetime import datetime

from pydantic import BaseModel


class WalletTransactionResponse(BaseModel):
    id: str
    transaction_type: str
    amount: float
    source: str | None = None
    reference_id: str | None = None
    description: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class WalletBalanceResponse(BaseModel):
    balance: float
