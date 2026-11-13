from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.routers import analysis, backtest, calculator, compare, currencies, forecast, health, indicators, opportunities, portfolio, rates

app = FastAPI(
    title=settings.app_name,
    description=(
        "Quantitative currency intelligence API: historical FX data, technical indicators, "
        "volatility/mean-reversion/trend analysis, probabilistic forecasting, a transparent "
        "buying-opportunity scoring engine, and walk-forward backtesting. See /docs for the "
        "full interactive schema."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(currencies.router)
app.include_router(rates.router)
app.include_router(compare.router)
app.include_router(opportunities.router)
app.include_router(analysis.router)
app.include_router(forecast.router)
app.include_router(indicators.router)
app.include_router(calculator.router)
app.include_router(portfolio.router)
app.include_router(backtest.router)
app.include_router(health.router)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
