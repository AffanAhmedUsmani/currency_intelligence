# Currency Intelligence

A quantitative currency comparison and buying-opportunity decision-support platform. Pick a base
currency (default PKR), compare it against ~20 other currencies over a selectable historical
window, and get a transparent, explainable "buy / wait / avoid" read on each one — backed by real
historical FX data, standard technical/volatility/mean-reversion analysis, a bootstrap-based
probabilistic forecast, and a walk-forward backtest that checks whether the core signal has
actually had any historical value, instead of just asserting it does.

**This is a decision-support tool, not financial advice.** Every recommendation ships with its
supporting evidence, contradicting evidence, risks, and what would invalidate it.

---

## 1. Architecture

```
currency-intel/
├── backend/     FastAPI + Python quantitative engine (the "brain")
└── frontend/    React + TypeScript + Vite UI (the "presentation layer")
```

- **Backend** owns all data retrieval, caching, and every calculation: technical indicators,
  volatility, mean-reversion, trend/momentum, forecasting, the opportunity scoring engine, and
  backtesting. The frontend never computes anything financial — it only renders what the API
  returns.
- **Frontend** is deliberately a single, minimal flow rather than a dashboard with many controls:
  a nav bar (base currency, amount, chart period, Analyze), an auto-computed "Best 5 currencies to
  invest in" basket with holding-period tabs (1 Month/3 Months/6 Months/1 Year) showing how the
  split, risk level, and expected outcome change by horizon, and a grid of every currency's own
  chart below it. Clicking any currency (in the grid or elsewhere) opens a full-screen detail view
  (chart + indicator/volatility/mean-reversion/forecast/backtest tabs) for anyone who wants to go
  deeper — the complexity is there on demand, not on the surface. Dark/light theme, responsive
  down to phone width.

### Why these specific technical choices

- **SQLite, not Postgres/Redis.** This is a single-user local app. A SQL cache table
  (`rate_observations`) plus a short-TTL in-memory dict for "latest" lookups gets the same
  practical behavior (persistent historical cache, fast repeated reads) with zero infrastructure
  to stand up. Swapping in Postgres later is a one-line `DATABASE_URL` change since the data layer
  goes through SQLAlchemy.
- **Two FX data providers, not one.** See §2 — no single free provider covers both "deep reliable
  history" and "PKR / Gulf currencies", so the app uses both behind a common interface.
- **Bootstrap Monte Carlo, not GARCH/ARIMA.** See §4.5 — a documented, deliberate scope decision,
  not an oversight.

---

## 2. Data providers

| Provider | What it is | Coverage | Rate type | Used for |
|---|---|---|---|---|
| **Frankfurter** (`api.frankfurter.dev`) | Official ECB daily reference rates | ~30 major/regional currencies (EUR, USD, GBP, JPY, AUD, CAD, CNY, INR, TRY, …) — **no PKR, no Gulf currencies** | `reference` (official daily fixing) | Preferred source whenever both legs of a pair are in its list |
| **Yahoo Finance chart API** | Unofficial but public FX cross-rate feed (same endpoint the `yfinance` library scrapes) | Effectively any 3-letter currency, including PKR, LKR, BDT, NGN, EGP, and the Gulf pegs | `indicative` | Fallback for everything Frankfurter doesn't cover — which, for this app's headline use case (PKR), is **every single comparison currency** |

This matters because **ECB/Frankfurter does not publish a PKR rate at all.** A PKR-centric app
built only on "official" free FX APIs (Frankfurter, most others) simply cannot answer the
product's core question. The Yahoo endpoint is unofficial and could change or rate-limit without
notice — that's exactly why it sits behind the same `RateProvider` interface as Frankfurter
(`backend/app/providers/base.py`), with an aggregator (`providers/aggregator.py`) that prefers
Frankfurter when available and transparently falls back otherwise. Every API response reports
which provider actually served the data and whether it's a `reference` or `indicative` rate — the
app never claims Yahoo's indicative cross-rate is an official fixing.

**Providers considered and not used:** Open Exchange Rates and CurrencyLayer both gate historical
data and most currencies behind a paid tier; ExchangeRate-API's free "open access" endpoint only
serves *latest* rates, not history; Alpha Vantage covers PKR but needs an API key and a 25
req/day free limit, too restrictive for a comparison of ~20 currencies per request. None were
viable as a **free, keyless, history-capable, PKR-covering** source on their own.

**Known data-quality caveat:** because PKR/Gulf-currency series come from an unofficial feed, you
may occasionally see a single-day spike-and-revert in the raw price line for thinly-traded pegged
currencies (BHD, OMR, KWD, QAR) when their USD cross has a noisy tick on Yahoo's side — this is
genuine upstream data, not a bug in the triangulation math (verified against the raw provider
response). It's visually obvious against the smoothed moving-average overlays in the detail view.
The app does not silently filter or "fix" this, per the project's non-negotiable: never fabricate
or quietly alter observed historical data.

---

## 3. Running it

### Option A — local dev (recommended for iterating)

**Backend** (needs Python 3.11+; developed against 3.13):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # no API keys needed — defaults are fine
uvicorn app.main:app --reload --port 8000
```

Visit `http://127.0.0.1:8000/docs` for interactive OpenAPI docs, or `http://127.0.0.1:8000/api/health`
to confirm both providers are reachable.

**Frontend** (needs Node 18+):

```bash
cd frontend
npm install
cp .env.example .env          # leave VITE_API_BASE_URL empty — dev proxy handles it
npm run dev
```

Visit `http://localhost:5173`. The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`
(see `vite.config.ts`), so no CORS configuration is needed in dev.

### Option B — Docker Compose

```bash
docker compose up --build
```

Frontend at `http://localhost:5173`, backend at `http://localhost:8000`. The backend's SQLite
cache persists in a named Docker volume (`backend_data`) across restarts.

### Running tests

```bash
cd backend
pytest -q
```

44 tests cover: indicator correctness against hand-computed values (SMA, RSI boundary behavior,
MACD histogram identity, Bollinger band ordering, max drawdown, log returns), opportunity-score
classification thresholds and edge cases (data-quality gating, risk gating, "rising currency
should never score as a decline opportunity"), the backtest module (correctly finds edge on a
synthetic mean-reverting series, degrades gracefully on a pure random walk, and is explicit about
insufficient-data cases rather than fabricating a result), the holding-period forecast's round-trip
direction (a currency trending toward "cheaper" must project as a loss, not a gain — this caught a
real bug during development), and the portfolio optimizer's correctness (diversification actually
lowers risk for uncorrelated assets, perfectly-correlated assets trigger a warning and show zero
diversification benefit, target-return clamping, exact allocation totals, and the minimum-variance
portfolio having the lowest risk of any achievable target — this test suite caught a second real
sign-convention bug, in the optimizer's expected-return input, before it shipped).

---

## 4. Methodology

### 4.0 The analytical reference window is fixed at ~2 years, independent of what's displayed

`lookback_days_for()` (`backend/app/services/analysis_engine.py`) always fetches at least
`ANALYTICAL_LOOKBACK_DAYS = 730` days of history and feeds *all* of it into every indicator,
volatility, mean-reversion, forecast, and backtest calculation — this is deliberately decoupled
from whatever period a UI is displaying or targeting. Earlier builds scaled the fetched history to
roughly match the selected period (e.g. a 1-month view only pulled ~220 days), which meant z-scores,
volatility percentiles, the AR(1) mean-reversion fit, the bootstrap forecast, and the backtest's
signal count were all built on a shorter, inconsistent sample depending on what the user happened
to be looking at. A 1-month holding-period projection and a 1-year one for the same pair now draw
from the exact same ~2-year statistical foundation; `period`/`holding_period` only controls what's
*displayed* (the chart slice, the pct-change headline, the forecast/projection horizon) on top of
that shared foundation. The frontend's nav bar has no period selector for this reason — there's
nothing for it to control upstream of the analysis anymore. A per-currency period selector remains
inside the detail view purely to change what's *shown* (zoom the chart, pick a forecast horizon),
not what the underlying statistics are computed from.

### 4.1 Technical indicators (`backend/app/analytics/indicators.py`)

SMA (7/14/30/50/200d), EMA(20), Wilder's RSI(14), MACD(12/26/9), Bollinger Bands(20, 2σ), ROC,
momentum. **ATR and the stochastic oscillator are implemented as close-price proxies**, not
canonical OHLC indicators — every data provider available to this app returns daily *close* rates
only, with no intraday high/low. This is labeled explicitly everywhere these two surface in the
API and UI rather than silently presenting a proxy as the textbook indicator.

### 4.2 Volatility (`analytics/volatility.py`)

Rolling annualized volatility, EWMA (RiskMetrics-style, λ=0.94) annualized volatility, volatility
percentile (where does *today's* vol sit vs. its own history), max drawdown, downside deviation.
The point: a currency can get cheaper in an orderly, low-volatility way, or in a chaotic,
high-volatility way — these are different situations and the scoring engine treats them
differently.

### 4.3 Mean reversion (`analytics/meanreversion.py`)

Rolling z-score vs. a trailing mean, Bollinger-band position, and an AR(1) fit on deviations from
the rolling mean to estimate a half-life — but critically, the module computes a t-statistic on
the AR(1) coefficient and only reports mean-reversion as `is_statistically_supported: true` when
there's real evidence for it (0 < φ < 0.98 and |t| > 2). **A large z-score alone is not treated as
evidence of an impending bounce** — on a trending/non-reverting series it's flagged as a risk, not
a signal, exactly per the brief's warning against assuming every pair reverts.

### 4.4 Trend & momentum (`analytics/trend.py`)

Short-vs-long moving average direction, ROC-based acceleration/deceleration classification, and
moving-average crossover detection (bullish/bearish) as an early reversal signal.

### 4.5 Forecasting (`analytics/forecast.py`) — and why it's a bootstrap, not GARCH/ARIMA

The primary forecast method is a **bootstrap Monte Carlo simulation**: resample the currency's own
historical daily log returns (with replacement) thousands of times over the forecast horizon, and
report the resulting distribution (median move, probability of appreciation/depreciation, 90%
range) — not a single predicted price. A secondary Holt exponential-smoothing trend extrapolation
is included as a cross-check, clearly labeled supplementary, wrapped so it degrades to "omitted"
rather than crashing on short/degenerate series.

This project deliberately does **not** ship a full GARCH or ARIMA fit. Why: the academic
literature on exchange-rate forecasting (going back to Meese & Rogoff, 1983) is unusually blunt
that a naive random walk is an extremely hard benchmark to beat out-of-sample for daily FX, and
shipping an ARIMA/GARCH model here would mostly add the *appearance* of sophistication without
demonstrated forecasting value. The bootstrap approach is honest about the same underlying
reality — it describes a *range of plausible outcomes based on history*, not a prediction — and
critically, **`analytics/backtest.py` actually checks** whether any of this has had real
predictive value for a given pair, out-of-sample, rather than asserting it.

### 4.6 The Buying Opportunity Engine (`analytics/scoring.py`)

Combines seven signals into one 0–100 score using the weighted framework from the product brief:

| Component | Weight |
|---|---|
| Historical valuation deviation (z-score) | 20% |
| Short-term price decline | 15% |
| Mean-reversion evidence | 15% |
| Momentum improvement | 15% |
| Trend confirmation | 10% |
| Volatility / downside risk | 10% |
| Probabilistic forecast | 10% |
| Data quality / model confidence | 5% |

These weights are **explicitly treated as hypotheses, not validated truths** (per the brief) —
`backtest.py` is what actually checks whether the heaviest-weighted signal has historical value,
not this module. Classification into the five brief-specified categories (`STRONG BUY
OPPORTUNITY` → `AVOID FOR NOW`) is gated, not just thresholded: low data quality or extreme
volatility caps the result at `WAIT / MONITOR` even if the raw weighted score looks high, so the
engine can't call a crashing, chaotic currency a "buy" just because its z-score is extreme. Every
score ships with a generated, evidence-specific explanation: what's supporting it, what's
contradicting it, what the risks are, and what would invalidate the read (see
`_build_explanation` in `scoring.py`).

### 4.7 Holding-period projection (`analytics/forecast.py::simulate_holding_period_outcomes`)

The exchange calculator projects what converting an amount *now* and holding it would be worth
back in the base currency after 1/3/6/12 months, using the same bootstrap simulation as §4.5.
Reuses the simulated return paths to compute, per horizon: expected value, expected profit/loss,
a pessimistic-to-optimistic range (5th/95th percentile), and probability of profit — never a
single predicted number. Worth noting since it's easy to get backwards: the app's rate convention
is "1 unit of base = X units of target", so a *rising* rate means the target currency is getting
*cheaper* — bad for someone who already converted and is holding it. The round-trip math
(`value_later = amount × (1 − fee)² × exp(−cumulative_log_return)`) and its direction are each
covered by a dedicated test in `tests/test_forecast.py` (zero-drift ≈ break-even, upward rate
drift ⇒ projected loss, downward rate drift ⇒ projected gain) rather than asserted.

### 4.8 Multi-currency basket allocation (`analytics/portfolio.py`)

When the calculator has 2+ target currencies selected, it offers a "Suggested basket" allocation:
how to split the entered amount across those currencies so that, per the brief's request, if one
underperforms the others can offset it. This is a long-only, mean-variance (Markowitz-style)
optimization — minimize `w'Σw` subject to `w'μ = target`, `Σw = 1`, `0 ≤ w ≤ 1` — solved with
`scipy.optimize.minimize` (SLSQP), using each currency's own historical covariance against the
*others in the basket*, not just its own volatility in isolation. A user-adjustable "target profit
expectancy" slider controls `target`; the resulting weights are then characterized by a **joint**
bootstrap (same sampled calendar days applied to every currency per simulated path, preserving
real historical co-movement) to get the actual expected/pessimistic/optimistic/probability-of-profit
outcome, not just the analytic variance number.

Two things worth calling out because they were non-obvious and each had to be caught with a test
before shipping (`tests/test_portfolio.py`):

- **Sign convention.** The app's rate series is base→quote ("1 base = X quote"); a *rising* rate
  means the quote currency is getting *cheaper*. The optimizer's expected-return input is the
  negative of the rate's own drift (exact, via `log(1/x) = -log(x)`, not an approximation) — get
  this backwards and the optimizer *rewards* currencies that are losing value. Covariance is
  unaffected (`Cov(-X,-Y) = Cov(X,Y)`), so only the mean vector needed the sign fix.
- **The frontier has two branches.** Mean-variance risk is a parabola with its vertex at the
  minimum-variance portfolio — moving the target *away* from that point in *either* direction adds
  risk. "Higher target ⇒ higher risk" is only guaranteed once you're already above the
  minimum-variance portfolio's own return, which is why the UI slider's low end is pinned to that
  safe baseline rather than to the absolute worst achievable return — that's the branch a user
  dragging the slider upward is actually moving along, and it's the one where the risk/return
  trade-off the brief asked for ("more expectancy, more risk") actually holds.

`correlation_warnings` flags any pair of selected currencies whose historical daily moves
correlate above 0.9 — e.g. two currencies pegged to the same anchor — since combining them adds
little real diversification even though it looks like two assets. One important caveat on top of
the general PKR/Gulf-currency data-noise caveat in §2: because every PKR cross-rate here is
triangulated through USD, correlation estimates partly reflect the shared PKR/USD leg (which is
real, shared systemic risk for a PKR holder, not just noise) *and* partly reflect per-currency
feed noise for thinly-traded pairs — this can understate the true correlation between, say, two
Gulf pegs, so a lack of a warning is not a guarantee of genuine independence.

### 4.9 Backtesting (`analytics/backtest.py`)

Walk-forward validates the single most heavily-weighted, cheapest-to-vectorize signal — "is the
currency's rolling z-score below a threshold" — against the subsequent N-day return, compared to
an unconditional baseline (no look-ahead bias: the z-score at each date only uses data up to that
date; the *evaluation* window correctly looks forward, which is what a backtest is for). Reports
hit rate, average return, worst subsequent move, and a Brier score for calibration, and is
explicit when a pair has too few historical signals to conclude anything.

**Stated limitation:** this backtests the single largest component of the opportunity score, not
the full eight-component weighted formula end-to-end (a live walk-forward re-run of the entire
pipeline, including a fresh bootstrap simulation, at every historical date was judged too
expensive for an interactive API). This is surfaced in the API response and here, not hidden.

### 4.10 Walk-forward backtest of the actual weekly-rotation strategy (`analytics/weekly_rotation_backtest.py`)

§4.9's backtest validates one pair's signal in isolation. This module instead backtests the
*workflow* the app's basket feature is built to support: every `rebalance_days`, rotate into
whichever `top_n` candidates currently look statistically cheapest (by the same z-score), hold,
then rotate again — exactly the "enter an amount weekly, buy the suggested currencies, convert
back, repeat" pattern a real user would follow. At each historical rebalance checkpoint the pick
is made from data available only up to that date (no look-ahead), then the realized return to the
next checkpoint is measured and compared against the honest benchmark of equally diversifying
across *every* candidate every period — this isolates whether the selection itself has value, not
just whether currencies move. `GET /api/backtest/weekly-rotation` exposes it; the "How reliable is
this, historically?" panel on the live page surfaces it with an adjustable rebalance interval and
fee.

**The most important finding from building this:** at a 1.5% round-trip fee and weekly rebalancing,
the backtest's cumulative return is dominated by the mechanical cost of trading, not by whether the
signal works. Concretely, for PKR against the major-currency universe: at 0% fees the strategy shows
a real, modest edge over the diversified benchmark (+7.8% vs. -0.3% cumulative over the test window,
50% win rate); at a realistic 1.5% round-trip fee, both the strategy and the benchmark lose roughly
-88% cumulatively over the same ~72 weekly rebalances — because `(1 - 0.03)^72 ≈ 0.11`, i.e. paying a
3% round-trip cost 72 times in a row only leaves ~11% of the original capital *before accounting for
any price movement at all*. The UI's "Fee impact check" box computes and shows this pure-fee-drag
number next to the actual result specifically so this isn't hidden inside one cumulative percentage.
**Practical implication for literally doing this weekly:** the trading signal has to clear a very
high bar — your actual round-trip conversion cost — before it's worth doing more often than roughly
monthly; rotating weekly at typical retail FX spreads is very likely to lose money to fees alone,
independent of how good the underlying currency selection is.

### A note on a bug this backtesting effort found

Building §4.10 caught a real, pre-existing sign error in `scoring.py` that had been present since
the scoring engine was first written — found because a synthetic test with a *known* correct answer
failed, not because anyone suspected it. The app's rate series is base→quote (quote units per 1 base
unit); a **rising** rate means the quote currency is getting **cheaper** (you get more of it per
unit of base currency), which is the buy-favorable direction. `score_valuation_deviation`,
`score_short_term_decline`, `score_mean_reversion`, and `score_probabilistic_forecast` had this
backwards — rewarding a currency for currently being *expensive* relative to its own history, not
cheap — and the UI's narrative text ("X has declined...") inherited the same confusion. The original
`backtest.py` (§4.9) had the identical bug in both its entry-signal direction and its forward-return
formula. All of these are fixed now, each with a direction-locking test that asserts the specific,
derived-from-first-principles correct sign (`tests/test_scoring.py`, `tests/test_backtest.py`,
`tests/test_weekly_rotation_backtest.py`) rather than just re-asserting whatever the code happened
to output. It went undetected for as long as it did because the existing unit tests were written
under the same wrong mental model as the bug, so they *confirmed* it rather than catching it — the
lesson being that a synthetic test needs its expected answer derived independently of the
implementation, not read off a first draft of it.

---

## 5. API reference

Full interactive docs at `/docs` (Swagger) once the backend is running. Summary:

| Endpoint | Purpose |
|---|---|
| `GET /api/currencies` | Supported currency universe + metadata (name, flag, liquidity tier) |
| `GET /api/rates/latest` | Latest rates for a base against a list of quotes |
| `GET /api/rates/historical` | Raw historical series for one pair |
| `GET /api/compare` | The main dashboard payload: market summary + ~20 currency cards for a base/period/universe |
| `GET /api/opportunities` | Top-N ranked buying opportunities across a universe |
| `GET /api/analysis/{base}/{target}` | Full detail bundle: indicators, volatility, mean-reversion, trend, forecast, opportunity score, backtest |
| `GET /api/forecast/{base}/{target}` | Just the probabilistic forecast |
| `GET /api/indicators/{base}/{target}` | Just the technical indicator series |
| `POST /api/calculator` | Practical conversion calculator with fee handling, scenario analysis, and holding-period profit/loss projections |
| `POST /api/portfolio/optimize` | Mean-variance basket allocation across 2+ target currencies, with a user-adjustable target-return/risk slider |
| `GET /api/backtest/weekly-rotation` | Walk-forward backtest of rotating into the top-N statistically cheapest currencies on a schedule, vs. diversifying across everyone |
| `GET /api/health` | Provider + database health check |

The currency universe (`backend/app/services/currency_universe.py`) is a plain config dict, not
hardcoded into the analytics engine — adding a currency is a one-line addition there.

---

## 6. Known limitations (stated, not hidden)

- **SQLite + in-process cache**, not Postgres/Redis — fine for single-user local use; swap
  `DATABASE_URL` for Postgres if this needs to serve multiple users concurrently.
- **Yahoo Finance provider is unofficial** and could break or rate-limit without notice; the
  provider abstraction makes swapping/adding a provider straightforward if it does.
- **PKR/Gulf-currency history can show single-day data noise** from the upstream feed (see §2).
- **No GARCH/ARIMA** — bootstrap Monte Carlo + backtested z-score signal instead, by design (§4.5).
- **Backtest validates the top component signal, not the full 8-component score** end-to-end (§4.7).
- **ATR/stochastic are close-price proxies**, not canonical OHLC indicators — no provider here
  returns intraday high/low.
- Cache coverage-checking is boundary-based (checks the start/end of a requested window, not
  every interior day) — correct for daily data with occasional weekend/holiday gaps, but not a
  guarantee against an isolated interior gap going unnoticed on an already-cached range.

## 7. Non-negotiables this build honors

No hardcoded exchange rates anywhere in the app — every number on screen traces back to a live
provider fetch or its SQLite cache. Every chart, card, and score recomputes from the selected base
currency and period (verified: switching base currency, period, or universe triggers a fresh
`/api/compare` call; the detail modal has its own independent period selector). Recommendations
are generated from the transparent weighted-component formula in §4.6, never a flat "price fell ⇒
buy" rule. Forecasts always ship with a confidence level and an uncertainty range, never a bare
point prediction. Rate type (`reference` vs `indicative`) and data provider are surfaced on every
response that includes a rate.

---

## 8. Deploying to Vercel + Render

**Why two platforms, not just Vercel:** Vercel is excellent for the frontend (static Vite build,
free, trivial setup) but its serverless functions are the wrong fit for the backend specifically —
they're stateless per-invocation (our SQLite historical-rate cache needs a filesystem that persists
across requests, not one that resets every call) and time-limited (a cold `/api/compare` across 20
currencies or the weekly-rotation backtest can take 15-20s, over Vercel Hobby's default limit). So:
**frontend on Vercel, backend on Render** (or Railway/Fly — anything that runs a long-lived
container). This is the standard split for this shape of app, not a workaround.

### 8.1 Backend → Render

1. Push this repo to GitHub (already done if you're reading this from a clone with a remote).
2. Go to [Render's Blueprints page](https://dashboard.render.com/blueprints) → **New Blueprint
   Instance** → connect this repo. Render reads `render.yaml` at the repo root automatically and
   provisions a free Docker web service from `currency-intel/backend`'s existing `Dockerfile` — no
   manual service configuration needed.
3. Wait for the first deploy to finish, then copy the service's URL (something like
   `https://currency-intelligence-api.onrender.com`). Confirm it's alive:
   `curl https://<your-service>.onrender.com/api/health`.
4. **Free-tier caveat:** Render's free web services spin down after ~15 minutes of inactivity. The
   next request after that wakes it back up but takes 30-60s. Fine for a personal/demo deployment;
   upgrade to a paid instance (or ping it periodically) if that cold start is a problem for you.

### 8.2 Frontend → Vercel

1. [Import the repo](https://vercel.com/new) into Vercel. Since this is a monorepo, set **Root
   Directory** to `currency-intel/frontend` on the import screen (Vercel auto-detects Vite from
   there via `vercel.json`/`package.json` — no other build settings needed).
2. Before the first deploy (or after, then redeploy), add an environment variable:
   **`VITE_API_BASE_URL`** = your Render URL from §8.1 (e.g. `https://currency-intelligence-api.onrender.com`,
   no trailing slash). This is a *build-time* Vite variable (see `src/api/client.ts`), so changing
   it always requires a redeploy, not just a restart.
3. Deploy. You'll get a `https://<project>.vercel.app` URL.

### 8.3 Close the loop: CORS

The backend only accepts browser requests from origins listed in `CI_CORS_ORIGINS`. Once you have
your real Vercel URL from §8.2, go back to the Render service → **Environment** → update
`CI_CORS_ORIGINS` to `["https://<your-project>.vercel.app"]` (a JSON array, as a string) and let it
redeploy. Until you do this, the deployed frontend will load but every API call will fail with a
CORS error in the browser console — if that happens, this step is almost certainly why.

### 8.4 Updating after this point

Both platforms auto-deploy on push to your default branch (Render via the Blueprint, Vercel via
its GitHub integration) — `git push` is the whole update workflow afterward. No action needed for
most changes; re-run §8.3 only if the Vercel URL itself ever changes (e.g. a new project).
