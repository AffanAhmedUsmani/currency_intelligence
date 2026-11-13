"""Multi-currency basket allocation.

The idea: instead of putting an entire amount into one currency, spread it
across the currencies the user selected so that if one underperforms, the
others can offset it — classic diversification, applied to a PKR-holder's
FX purchase decision rather than a stock portfolio.

Method (deliberately mirrors standard mean-variance portfolio theory rather
than a made-up heuristic, since this is exactly the problem it was built
for — just long-only, since you can't short a currency purchase here):

1. Align the selected currencies' own historical daily returns on their
   common trading dates (inner join) — this is what lets us measure how
   much they actually move *together*, not just how volatile each is on
   its own. Two currencies pegged to the same anchor (e.g. BHD and QAR,
   both pegged to USD) will show up as ~100% correlated here, and
   `correlation_warnings` calls that out explicitly, because mixing two
   near-identical currencies adds little real diversification even though
   it looks like "2 currencies" on paper.
2. Scale the daily mean/covariance to the user's chosen holding horizon
   (variance scales ~linearly with time for iid daily returns — the same
   approximation the rest of this app uses for annualized volatility).
3. Solve a long-only (0 <= weight <= 1, weights sum to 1) minimum-variance
   allocation for a given target return via `scipy.optimize.minimize`
   (SLSQP) — the same constrained QP structure as a textbook Markowitz
   problem, just without allowing negative (short) weights, because this
   is "how should I split a currency purchase", not a hedge fund.
4. Once weights are chosen, characterize what they'd *actually* have done
   historically with a joint bootstrap: resample calendar days (not
   per-currency returns independently) so each simulated path keeps the
   real historical co-movement between the selected currencies, then
   compound each currency's return over that same sampled path. This is
   the same bootstrap philosophy as `forecast.py`, extended to multiple
   correlated series instead of one.

Not claimed: that this is dynamically-rebalanced, continuously-optimal
portfolio management, or that past correlation will hold going forward.
It's a single up-front allocation based on historical behavior, exactly
like every other projection in this app.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

MIN_COMMON_DAYS = 30
HIGH_CORRELATION_THRESHOLD = 0.9


@dataclass
class ReferencePortfolio:
    weights: dict[str, float]
    expected_return_pct: float
    volatility_pct: float


@dataclass
class PortfolioOutcome:
    expected_value: float
    expected_profit_loss: float
    expected_profit_loss_pct: float
    optimistic_value: float
    optimistic_profit_loss: float
    pessimistic_value: float
    pessimistic_profit_loss: float
    prob_profit_pct: float


@dataclass
class AllocationEntry:
    code: str
    weight_pct: float
    amount: float
    individual_expected_return_pct: float
    individual_volatility_pct: float


@dataclass
class PortfolioResult:
    codes: list[str]
    horizon_days: int
    n_common_days: int
    achievable_return_min_pct: float
    achievable_return_max_pct: float
    requested_target_return_pct: float | None
    effective_target_return_pct: float
    was_clamped: bool
    analytic_volatility_pct: float
    risk_level: str
    allocation: list[AllocationEntry] = field(default_factory=list)
    min_risk_portfolio: ReferencePortfolio | None = None
    max_return_portfolio: ReferencePortfolio | None = None
    outcome: PortfolioOutcome | None = None
    correlation_warnings: list[str] = field(default_factory=list)
    note: str = ""


def _risk_level(volatility_pct: float) -> str:
    if volatility_pct < 5:
        return "Low"
    if volatility_pct < 10:
        return "Moderate"
    if volatility_pct < 20:
        return "High"
    return "Very High"


def _min_variance_weights(cov: np.ndarray, n: int) -> np.ndarray:
    w0 = np.full(n, 1.0 / n)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0)] * n
    result = minimize(
        lambda w: float(w @ cov @ w), w0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 200, "ftol": 1e-12},
    )
    return result.x if result.success else w0


def _target_return_weights(cov: np.ndarray, mu: np.ndarray, target: float, n: int) -> np.ndarray:
    w0 = np.full(n, 1.0 / n)
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: float(w @ mu) - target},
    ]
    bounds = [(0.0, 1.0)] * n
    result = minimize(
        lambda w: float(w @ cov @ w), w0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 200, "ftol": 1e-12},
    )
    if result.success:
        return result.x
    # Fall back to whichever single asset is closest to the target — always feasible.
    closest = int(np.argmin(np.abs(mu - target)))
    w = np.zeros(n)
    w[closest] = 1.0
    return w


def _joint_bootstrap_outcome(
    log_rate_returns: pd.DataFrame, weights: np.ndarray, amount: float, fee_pct: float,
    horizon_days: int, n_sims: int = 2500,
) -> PortfolioOutcome:
    """`log_rate_returns` is in the app's base->quote RATE convention (see
    forecast.py's module docstring): a RISING rate means the quote currency
    is getting CHEAPER, which is a loss for someone holding it. The log
    return of *holding value* is therefore the negative of the rate's log
    return — exactly (not approximately, since log(1/x) = -log(x)).
    """
    rng = np.random.default_rng()
    t = len(log_rate_returns)
    value_log_vals = -log_rate_returns.to_numpy()  # (T, N) — log return of VALUE, not of the rate
    sampled_idx = rng.integers(0, t, size=(n_sims, horizon_days))  # same days across all currencies per path
    sampled_log = value_log_vals[sampled_idx]  # (n_sims, horizon_days, N)
    cum_growth = np.exp(sampled_log.sum(axis=1))  # (n_sims, N) = compounded value-growth factor per currency per sim

    portfolio_factor = cum_growth @ weights  # (n_sims,)
    fee_mult_sq = (1.0 - fee_pct / 100.0) ** 2
    terminal_value = amount * fee_mult_sq * portfolio_factor
    profit = terminal_value - amount

    return PortfolioOutcome(
        expected_value=float(np.median(terminal_value)),
        expected_profit_loss=float(np.median(profit)),
        expected_profit_loss_pct=float(np.median(profit) / amount * 100.0),
        optimistic_value=float(np.percentile(terminal_value, 95)),
        optimistic_profit_loss=float(np.percentile(profit, 95)),
        pessimistic_value=float(np.percentile(terminal_value, 5)),
        pessimistic_profit_loss=float(np.percentile(profit, 5)),
        prob_profit_pct=float((profit > 0).mean() * 100.0),
    )


def _round_allocation(codes: list[str], weights: np.ndarray, amount: float, unit: float = 1000.0) -> list[dict]:
    raw = weights * amount
    order = np.argsort(-weights)  # largest weight first
    rounded = np.floor(raw / unit) * unit
    largest_idx = order[0]
    rounded[largest_idx] += amount - rounded.sum()  # remainder absorbs rounding, keeps exact total
    return [{"code": codes[i], "amount": float(rounded[i])} for i in order]


def build_portfolio(
    returns_by_code: dict[str, pd.Series],
    amount: float,
    fee_pct: float,
    horizon_days: int,
    target_return_pct: float | None,
) -> PortfolioResult:
    df_log = pd.DataFrame(returns_by_code).dropna(how="any")
    codes = list(df_log.columns)
    n = len(codes)
    n_common_days = len(df_log)

    if n_common_days < MIN_COMMON_DAYS:
        raise ValueError(
            f"Only {n_common_days} overlapping trading days across {codes} — need at least "
            f"{MIN_COMMON_DAYS} for a responsible allocation."
        )

    # Covariance/correlation are sign-invariant under a uniform negation (Cov(-X,-Y) = Cov(X,Y)),
    # so it's fine to compute them straight from the RATE's simple returns. The MEAN must not be —
    # see `_joint_bootstrap_outcome`'s docstring for why value return = -(rate return) exactly.
    df_simple = np.expm1(df_log)
    df_value_simple = np.expm1(-df_log)
    mu_daily = df_value_simple.mean().to_numpy()
    cov_daily = df_simple.cov().to_numpy()
    corr = df_simple.corr()

    mu_h = (1.0 + mu_daily) ** horizon_days - 1.0
    cov_h = cov_daily * horizon_days

    achievable_min, achievable_max = float(mu_h.min()), float(mu_h.max())

    was_clamped = False
    if target_return_pct is None:
        weights = _min_variance_weights(cov_h, n)
        effective_target = float(weights @ mu_h)
    else:
        target_frac = target_return_pct / 100.0
        clamped = min(max(target_frac, achievable_min), achievable_max)
        was_clamped = abs(clamped - target_frac) > 1e-9
        weights = _target_return_weights(cov_h, mu_h, clamped, n)
        effective_target = float(weights @ mu_h)

    volatility_pct = float(np.sqrt(max(weights @ cov_h @ weights, 0.0)) * 100.0)

    min_var_w = _min_variance_weights(cov_h, n)
    max_idx = int(np.argmax(mu_h))
    max_return_w = np.zeros(n)
    max_return_w[max_idx] = 1.0

    def ref_portfolio(w: np.ndarray) -> ReferencePortfolio:
        return ReferencePortfolio(
            weights={codes[i]: float(w[i] * 100.0) for i in range(n)},
            expected_return_pct=float(w @ mu_h * 100.0),
            volatility_pct=float(np.sqrt(max(w @ cov_h @ w, 0.0)) * 100.0),
        )

    allocation_raw = _round_allocation(codes, weights, amount)
    idx_by_code = {c: i for i, c in enumerate(codes)}
    allocation = [
        AllocationEntry(
            code=a["code"],
            weight_pct=float(weights[idx_by_code[a["code"]]] * 100.0),
            amount=a["amount"],
            individual_expected_return_pct=float(mu_h[idx_by_code[a["code"]]] * 100.0),
            individual_volatility_pct=float(np.sqrt(cov_h[idx_by_code[a["code"]], idx_by_code[a["code"]]]) * 100.0),
        )
        for a in allocation_raw
    ]

    correlation_warnings = []
    for i in range(n):
        for j in range(i + 1, n):
            c = corr.iloc[i, j]
            if pd.notna(c) and c > HIGH_CORRELATION_THRESHOLD:
                correlation_warnings.append(
                    f"{codes[i]} and {codes[j]} have moved together {c * 100:.0f}% of the time in this "
                    f"history (often a sign both are pegged to the same anchor currency) — holding both "
                    f"adds little real diversification versus holding just one."
                )

    outcome = _joint_bootstrap_outcome(df_log, weights, amount, fee_pct, horizon_days)

    note = (
        "Allocation is a one-time split based on historical mean/variance/correlation, not a dynamically "
        "rebalanced strategy. Past co-movement between currencies is not guaranteed to continue — "
        "diversification reduces, but never eliminates, the chance of an overall loss."
    )

    return PortfolioResult(
        codes=codes,
        horizon_days=horizon_days,
        n_common_days=n_common_days,
        achievable_return_min_pct=achievable_min * 100.0,
        achievable_return_max_pct=achievable_max * 100.0,
        requested_target_return_pct=target_return_pct,
        effective_target_return_pct=effective_target * 100.0,
        was_clamped=was_clamped,
        analytic_volatility_pct=volatility_pct,
        risk_level=_risk_level(volatility_pct),
        allocation=allocation,
        min_risk_portfolio=ref_portfolio(min_var_w),
        max_return_portfolio=ref_portfolio(max_return_w),
        outcome=outcome,
        correlation_warnings=correlation_warnings,
        note=note,
    )
