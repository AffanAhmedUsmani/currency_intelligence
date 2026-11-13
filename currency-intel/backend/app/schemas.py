from pydantic import BaseModel, Field


class CurrencyOut(BaseModel):
    code: str
    name: str
    flag: str
    liquidity_tier: int


class CalculatorRequest(BaseModel):
    base: str = Field(..., description="Currency the user holds, e.g. PKR")
    target: str = Field(..., description="Currency the user wants to buy, e.g. AUD")
    amount: float = Field(..., gt=0, description="Amount in base currency the user intends to spend")
    fee_pct: float = Field(0.0, ge=0, le=20, description="Transaction fee / spread, in percent")
    comparison_period: str = Field("1m", description="Period used for the historical comparison")


class HealthOut(BaseModel):
    status: str
    providers: dict
    database: str
