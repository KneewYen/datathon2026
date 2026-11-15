# PortfolioGuard AI technical documentation

## 1. Purpose and boundary

PortfolioGuard AI compares current and hypothetical allocations for fictional
investors. It is a decision-support prototype, not a trading system, portfolio
manager, tax calculator, or source of personalized financial advice. No component
can place or simulate the execution of a real order.

The system supports two flows:

1. **Persona scenario analysis** (`POST /api/analysis/persona/{persona}`): each
   persona has a strategy shift designed around what the case brief says they
   test. The original golden scenario, moving 20% of a TFSA from growth to dividend,
   remains the default `POST /api/analysis` request.
2. **Suitability challenge** (`POST /api/challenge`): the investor asks for a
   specific position, such as "Put 25% of my RRSP in NVDA". The system measures it
   as asked, a capped version and a diversified alternative, applies the persona's
   risk budget, and returns a verdict.

Both answer with historical observations, explicit assumptions, data provenance,
governance findings, and an observable agent trace.

## 2. System architecture

```text
Browser
  └─ Next.js dashboard
       ├─ POST /api/analysis/persona/{persona}
       │    └─ Global Orchestrator
       │         ├─ TFSA or RRSP Account Agent
       │         │    ├─ source Strategy Agent
       │         │    └─ destination Strategy Agent
       │         ├─ AWS Lambda: compare_strategy_shift (+ 2022 replay, robustness)
       │         ├─ Governance Agent (account scope + persona risk budget)
       │         └─ Explainability Agent → Amazon Bedrock Converse API
       └─ POST /api/challenge
            └─ Global Orchestrator
                 ├─ Request parser (deterministic, assets_universe.csv)
                 ├─ Suitability Challenge Agent (requested / capped / alternative)
                 ├─ AWS Lambda: compare_scenarios
                 ├─ Governance Agent (persona risk budget per scenario)
                 └─ Explainability Agent → Amazon Bedrock Converse API

Both Lambda operations read the versioned Amazon S3 dataset.
CloudWatch Logs receives structured Lambda lifecycle events with analysis and AWS
request identifiers. The API response exposes the same execution lineage to the UI.
```

Production code calls real AWS SDK clients. Missing AWS configuration or failed
cloud calls return a clear service error. The dashboard does not replace a failed
AWS response with locally fabricated metrics.

## 3. Agent hierarchy

### Global Orchestrator

The orchestrator validates typed input, resolves the persona and account, records
delegation, invokes the deterministic tool exactly once, applies governance, and
passes a closed evidence packet to explainability. It does not calculate metrics.

### Account agents

- **TFSA Account Agent:** coordinates the fictional TFSA comparison and discloses
  that eligibility, contribution room, and tax outcomes are out of scope.
- **RRSP Account Agent:** coordinates the fictional RRSP comparison and discloses
  that deductions, withdrawal taxation, and personal tax outcomes are out of scope.

Only the source and destination strategy agents are invoked for a shift. This keeps
delegation purposeful instead of calling decorative agents.

### Strategy agents

Eight strategy agents correspond to eight fictional baskets in
`backend/app/domain/presets.py`: growth, dividend, momentum, capital preservation,
ESG (ESGV, FTS.TO, CNR.TO), quality (CNR.TO, CSU.TO, MSFT, JNJ, PG), balanced index
(XIU.TO, SPY, XBB.TO, AGG) and crypto (BTC-USD, ETH-USD). Only the source and
destination agents of a shift are invoked. They return typed findings and requested
operations; they cannot invoke Bedrock or generate financial values.

### Suitability Challenge Agent

1. A deterministic parser extracts the asset (ticker or alias such as "bitcoin" or
   "Exxon") and the size: a stated percentage, a dollar amount divided by the
   fictional balance, or an assumed 10% that is disclosed as an assumption.
2. The agent builds up to four allocations from the persona's baseline:
   - the current portfolio;
   - the request as stated, funded proportionally from every sleeve;
   - a capped version. Its size solves `existing × (1 − w) + w = cap`, and it is
     omitted when the cap is zero or the asset is ESG-excluded;
   - the same amount in the persona's diversified alternative basket (growth for
     Amira, ESG for Mateo, quality for Robert).
3. One `compare_scenarios` Lambda call measures all of them on the same calendar.
4. Governance checks each scenario. The verdict is the first scenario within budget,
   in this order: requested (`aligned`), capped (`cap`), alternative
   (`alternative`), otherwise `conflict` (keep the current portfolio). A scenario
   that is close to the loss budget is flagged as a caution but not disqualified.

Mateo's challenge baseline is his ESG-screened allocation, so the screen starts
clean.

### Governance

Governance is deterministic. Account and evidence rules:

- simulation-only enforcement;
- TFSA and RRSP scope limits;
- agreement or disagreement between volatility and drawdown evidence;
- historical return trade-off disclosure;
- Amira concentration (HHI) control despite high risk tolerance;
- Mateo moderate-profile conflict and ESG controversy-evidence insufficiency;
- Robert short-horizon and capital-preservation conflict;
- robustness: `CONCLUSION_ROBUST` or `WINDOW_SENSITIVE`.

Fictional persona risk budgets, a documented demo policy:

| Control | Amira | Mateo | Robert |
| --- | ---: | ---: | ---: |
| 2022-replay loss budget | -40% | -25% | -15% |
| Single-company cap (requested asset) | 15% | 5% | 5% |
| Crypto cap | 10% | 0% | 0% |
| Longest acceptable recovery (half the minimum horizon) | 90 months | 48 months | 18 months |
| ESG sector exclusion (`assets_universe.csv` sector) | none | Energy | none |

Rules: `STRESS_BUDGET_EXCEEDED`, `STRESS_BUDGET_NEAR_LIMIT` (at least 90% of the
budget; a caution), `RECOVERY_EXCEEDS_HORIZON`, `RECOVERY_NOT_OBSERVED`,
`SINGLE_POSITION_CAP`, `CRYPTO_CAP_EXCEEDED`, `CRYPTO_OUTSIDE_PROFILE`,
`ESG_EXCLUSION_CONFLICT` and `ESG_SCREEN_PASSED`.

### Explainability: verified numbers

Bedrock receives the question, the investor context, the verdict or conclusion,
governance rule IDs with digits scrubbed from their messages, and the direction of
each change. Directions are given in risk words ("larger loss", "longer recovery")
so negative drawdowns cannot be misread. It never receives raw values.

The model writes digit-free prose. It may name "the 2022 selloff". The validator
rejects and retries, up to three attempts, if the prose contains digits, cites an
unknown evidence ID, or includes an unknown `{{token}}`. Forecast-like wording
about returns ("could offer higher returns") also triggers a retry. If that is the
only remaining issue after the retries, the answer is kept with an added
limitation.

The backend then appends a templated "Verified figures" sentence. Each figure is a
`{{token}}` resolved from the evidence registry built from Lambda output and the
persona budget. The response returns `answer_segments` and the `evidence`
registry, so the UI renders every number as a button showing its label, evidence
ID, raw value, formula version and S3 source. Earlier versions let the model place
tokens. In live tests Nova Lite attached one scenario's figure to another, so
figure placement was moved into code.

## 4. Request and response contracts

The primary request includes:

- persona: `amira`, `mateo`, or `robert`;
- account: `TFSA` or `RRSP`;
- two or more known strategy weights that sum to one;
- one source-to-destination strategy shift between strategies in the allocation;
- CAD base currency and an optional fictional portfolio value;
- an explicit historical date window.

Validation rejects unknown strategies, negative weights, totals that do not equal
one, impossible shifts, and invalid date order.

The response includes:

- analysis ID, question, persona, and account;
- current and proposed allocations;
- deterministic metrics with units, formula version, and source;
- cumulative performance series;
- account and strategy findings;
- governance rule IDs and severities;
- hierarchical trace with parent IDs and delegated agents;
- assumptions, limitations, S3 source objects, Bedrock model ID, and disclaimer.

## 5. Deterministic financial method

The current operation is `compare_strategy_shift`, formula version
`portfolio-risk-v1`.

### Allocation construction

The shift subtracts an exact percentage-point amount from the source strategy and
adds it to the destination. Strategy weights are expanded into asset weights using
versioned fictional basket definitions. Both levels must sum to one.

### Currency and calendar

- Adjusted close is used for returns.
- CAD listings use their adjusted close directly.
- USD listings are multiplied by the latest USD/CAD observation on or before the
  asset price date.
- The comparison uses only dates available for every holding.
- Fewer than 60 common observations fails validation.
- Portfolio weights are held constant, equivalent to daily rebalancing.

### Metrics

For daily portfolio returns `r` and 252 trading days per year:

- Annualized volatility: sample standard deviation of `r` multiplied by `sqrt(252)`.
- Historical annualized return: compounded growth raised to `252 / observations`,
  minus one.
- Total historical return: product of `(1 + r)` minus one.
- Maximum drawdown: minimum wealth-to-running-peak ratio minus one.
- Asset concentration: Herfindahl-Hirschman Index, the sum of squared asset weights.

Risk is classified as reduced only when annualized volatility falls and maximum
drawdown becomes less severe. If both worsen, risk is classified as increased;
otherwise the result is mixed.

### Primary fixture result

For 2023-11-13 through 2026-11-12, using 738 shared observations:

| Metric | Current | Proposed | Direction |
| --- | ---: | ---: | --- |
| Annualized volatility | 18.48% | 13.71% | Lower measured risk |
| Maximum drawdown | -19.72% | -15.53% | Less severe drawdown |
| Historical annualized return | 30.80% | 27.42% | Lower historical return |
| Asset concentration HHI | 0.1404 | 0.1144 | More diversified |

These are deterministic historical observations, not expected returns.

### Stress replay, recovery, and robustness

Both operations add:

- **2022 stress replay:** maximum drawdown and total return from 2022-01-01 to
  2022-12-31, when stocks and bonds fell together, plus the dollar loss on the
  fictional balance (`balance × stress drawdown`).
- **Months underwater:** on the full history, the worst peak-to-trough fall whose
  trough lies in 2022. The value is the months from that peak until wealth regains
  it, or `null` when the peak is not regained by the end of the data.
- **Robustness:** the same risk classification re-run on the full five-year
  history. The analysis is marked consistent when every window agrees.

`compare_scenarios` profiles two to six allocations. They share one calendar: the
dates common to all holdings across all scenarios. Each scenario returns evidence
items `scenario.<id>.<metric>` for volatility, drawdown, return, HHI, largest
position, requested-asset weight, the 2022 replay figures and months underwater.

### Persona scenario results (live AWS, 2023-11-13 to 2026-11-12)

| Persona | Shift | Conclusion | 2022 replay (current → proposed) | Recovery |
| --- | --- | --- | --- | --- |
| Amira | 20% growth → balanced index | risk reduced, return trade-off | proposed -25.9% vs -40% budget | 24 → 24 months |
| Mateo | 30% dividend → ESG | risk increased, ESG screen passed | proposed -22.7% vs -25% budget (near limit) | 18 → 19 months |
| Robert | 15% preservation → growth | risk increased | -8.7% → -14.7% vs -15% budget (near limit) | 8 → 15 months |

All three conclusions are robust on the full history.

### Challenge example (live AWS)

"Put 25% of my RRSP in NVDA" for Robert: as requested, the 2022 replay fell -22.4%
(-$100,981 on $450,000), beyond the -15% budget, and breached the 5% single-company
cap. Capped at 5%, it fell -11.2%. Verdict: `cap`. The same request from Amira is
also capped, at a 15% total NVDA position. Her "Should I buy Tesla?" is `aligned`.
Mateo's "Put 10% in Exxon" is ESG-excluded and resolves to the ESG `alternative`.
The system discloses that the ESG basket fell more in 2022 than the Exxon request
did.

## 6. Data provenance and quality controls

The AlphaForge starter dataset contains daily asset prices, USD/CAD observations,
corporate actions, macro series, source metadata, and an asset universe. The first
operation reads only `prices_daily.csv` and `fx_usdcad_daily.csv`.

Before upload, a committed manifest records filename, bytes, row count, SHA-256
digest, dataset ID, S3 prefix, and quality notes. S3 versioning is enabled. Lambda
loads the S3 manifest, verifies the dataset ID and prefix, and rejects either input
file when its byte count or SHA-256 digest differs. It returns each input and
manifest URI with its version ID or ETag so the result identifies the data it used.

The loader rejects:

- duplicate ticker dates or FX dates;
- non-positive adjusted closes or FX rates;
- missing tickers or requested history;
- unsupported currencies;
- unavailable prior FX observations.

Known limitations remain visible: selection and survivorship bias, fictional
strategy baskets, excluded fees/taxes/trading costs, and unsafe macro reference
dates. Macro data is not used for historical signals until publication dates or a
conservative lag policy are implemented.

## 7. AWS implementation

The deployed SAM stack defines:

- private, encrypted, versioned S3 storage with blocked public access;
- ARM64 Python Lambda with bounded timeout, memory, and reserved concurrency;
- Lambda read-only access to the dataset bucket;
- a 14-day CloudWatch Logs group;
- one unnamed least-privilege Lambda execution role with S3 reads limited to the
  dataset prefix and CloudWatch writes limited to the function log group;
- review-only IAM policy documents for exact backend Bedrock/Lambda access.

The workshop configuration is fixed to `us-east-1` and the system-defined
`us.amazon.nova-lite-v1:0` profile. IAM must allow its profile ARN plus Nova Lite in
`us-east-1`, `us-east-2`, and `us-west-2`; organization controls must also permit
all three destinations. Read-only role inventory found no suitable existing
application execution role. IAM simulation confirms that the participant role can
create, configure, pass, and delete the unnamed role in the stack, so deployment
uses `CAPABILITY_IAM` and remains gated by change-set review and explicit approval.

The initial change set was reviewed and separately approved before execution. The
stack reached `CREATE_COMPLETE`; the six dataset files and manifest were uploaded
and independently verified against S3-reported SHA-256 checksums and version IDs.
The Lambda has no event source, resource policy, function URL, or async destination.
One separately approved live invocation read the expected S3 object versions and
matched every local metric and all 93 performance points exactly. The function was
later updated in place (`aws lambda update-function-code`) with the
`compare_scenarios` operation and the stress and robustness outputs. Persona
analyses and challenges have been run end to end against the live Lambda and Bedrock
Nova Lite. Redeploying through SAM keeps the template and the function in sync.

## 8. Security and failure behavior

- No credentials are stored in source or requested in chat.
- Local development uses Workshop Studio temporary credentials through the AWS
  default credential chain and a named profile; credential values remain outside
  the repository and chat.
- S3 public access is blocked and data is encrypted at rest.
- Review policy documents scope IAM requirements to the calculation function,
  dataset prefix, log group, inference profile, and destination models.
- API input is schema validated.
- Bedrock cannot create or modify financial evidence.
- AWS configuration failures return HTTP 503; AWS execution failures return 502.
- No error path can trigger a transaction.

## 9. Verification

Local CI covers:

- request validation and API health;
- TFSA and RRSP delegation;
- observable parent/child agent trace;
- all three persona governance boundaries and risk-budget controls;
- request parsing (stated %, dollar amount, assumed size, no asset);
- persona-adaptive challenge verdicts (Robert NVDA `cap`, Amira Tesla `aligned`,
  Mateo Exxon `alternative` without a capped version);
- every rendered answer figure matching its evidence-registry display value;
- Bedrock evidence, token, numeric-claim and forecast-wording rejection;
- allocation invariants, duplicate-date safeguards, golden financial results,
  2022 stress and recovery calculation, and one-calendar scenario comparison;
- frontend lint and type-check.

The AWS acceptance test is opt-in and cannot pass through mocks. It must observe a
real Lambda request ID, versioned S3 sources, the configured Bedrock model ID, and a
grounded explanation.

## 10. Deferred work

After the real vertical slice is verified, planned work includes editable account
holdings, complete RRSP comparisons, VaR/CVaR, downside deviation, income analysis,
deeper momentum analytics, CloudWatch alarms/dashboard, prompt-injection tests,
and additional end-to-end persona scenarios.
