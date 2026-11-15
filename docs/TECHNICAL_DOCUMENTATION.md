# PortfolioGuard AI technical documentation

## 1. Purpose and boundary

PortfolioGuard AI compares current and hypothetical allocations for fictional
investors. It is a decision-support prototype, not a trading system, portfolio
manager, tax calculator, or source of personalized financial advice. No component
can place or simulate the execution of a real order.

The flagship end-to-end question is:

> I am considering buying $5,000 CAD of NVIDIA. Which account is a better fit, my TFSA or RRSP?

The system answers with historical observations, explicit assumptions, data
provenance, governance findings, and an observable agent trace.

## 2. System architecture

```text
Browser
  └─ Next.js dashboard
       └─ POST /api/investment-analysis
            └─ Cognito JWT → API Gateway HTTP API → FastAPI Lambda
                 └─ AWS Step Functions Standard
                      ├─ Global Orchestrator → Nova Lite
                      ├─ validated account-route Map
                      ├─ selected Account Orchestrators → Nova Lite
                      │    └─ validated specialist-route Map
                      ├─ selected Strategy Agents → Nova Lite
                      │    └─ validated authorized-tool Map + fixed Choice
                      ├─ selected deterministic Financial Tools Lambda calls
                      │    └─ versioned Amazon S3 dataset
                      ├─ deterministic coordinator + governance Lambda
                      └─ Explainability Agent → Nova Lite

CloudWatch Logs receives structured Lambda lifecycle events with analysis and AWS
request identifiers. Step Functions retains the actual state-transition history;
the API polls it and exposes the same execution lineage to the UI.
```

The hierarchy is implemented as executable AWS states, not decorative labels.
Global model output is validated into account Map items; each invoked account model
is validated into specialist Map items; each invoked specialist model is validated
into tool Map items. A fixed Choice state maps the four known operations to either
the financial Lambda or the research boundary. A model cannot provide a Lambda ARN
or arbitrary operation. Nonselected Map items do not exist and therefore do not
execute. The API returns a start response immediately and the dashboard polls the
Standard workflow until it returns a schema-validated final result.

PortfolioGuard uses direct Bedrock Runtime `Converse` calls with the system-defined
`us.amazon.nova-lite-v1:0` inference profile. It does not depend on Bedrock Agents
Classic. Every named agent has an allow-list of possible delegates and operations;
unsupported selections, numeric language-model claims, malformed JSON, or unknown
evidence IDs fail closed.

Every routing gate emits persisted delegation records containing the decision
maker, target, model-versus-policy source, rationale, parent event ID, selection,
actual invocation status, and evidence IDs. The dashboard renders those records
alongside actual execution events. Mandatory holdings exposure and purchase
simulation cannot be silently omitted: deterministic policy assigns each missing
operation to an account-permitted specialist and labels the assignment
`mandatory_policy`. Failed mandatory tools produce a partial account result and no
missing evidence is invented.

### Demo authentication and bounded access

The AWS endpoint uses API Gateway's native JWT authorizer with a Cognito issuer.
The Next.js client performs Authorization Code + PKCE against a public Cognito app
client (`GenerateSecret: false`). The PKCE verifier and access token live only in
browser session storage; no reusable secret or AWS credential is compiled into the
frontend. The access token expires after sixty minutes.

Local development remains simple: when the four Cognito public configuration
values are absent, the frontend calls local FastAPI without an authorization
header. In the AWS demo configuration, the dashboard is gated until sign-in and
every API request carries the access token. API Gateway validates issuer and
audience before invoking Lambda.

API stage throttling is one request per second with burst two. The API Lambda has
reserved concurrency two, the financial Lambda retains its deployed concurrency
five, and the Standard workflow has a 180-second execution timeout. Pydantic limits
question length and investor identifiers, while production error responses do not
return provider exception strings or internal ARNs.

Production code calls real AWS SDK clients. Missing AWS configuration or failed
cloud calls return a clear service error. The dashboard does not replace a failed
AWS response with locally fabricated metrics.

## 3. Agent hierarchy

### Global Orchestrator

The deterministic preparation step parses typed purchase intent and establishes
candidate account scope. The Global AI Orchestrator selects account agents through
Nova Lite. Explicit user account scope is a mandatory boundary; generic questions
allow the model to choose one or more candidate accounts. A routing validator
records every candidate and passes only selected/enforced account routes to the
Step Functions Map. The orchestrator does not calculate financial values.

### Account agents

- **TFSA Account Agent:** coordinates the fictional TFSA comparison and discloses
  that eligibility, contribution room, and tax outcomes are out of scope.
- **RRSP Account Agent:** coordinates the fictional RRSP comparison and discloses
  that deductions, withdrawal taxation, and personal tax outcomes are out of scope.

TFSA may delegate to Growth and Momentum; RRSP may delegate to Dividend and Capital
Preservation. Only model-selected specialists execute unless deterministic safety
coverage requires a missing specialist. Each specialist requests a subset of its
runtime-enforced tool allowlist. Nonselected specialists and tools are persisted as
`not_invoked` rather than inferred from a static diagram.

### Deterministic investment tools

- `analyze_holdings_exposure` values direct holdings and covered QQQ/SPY indirect
  NVIDIA exposure independently.
- `market_snapshot` reports the latest dataset close converted to CAD plus trailing
  historical returns, volatility, and drawdown; it is not a real-time quote.
- `simulate_account_purchase` compares each account before and after a hypothetical
  fractional-share purchase without changing total portfolio value or executing an order.
  It also reports target/portfolio correlation and the direct target position's
  covariance-based contribution to portfolio return variance when history is sufficient.

The ETF fixture is offline, versioned, and records issuer URL and as-of date. A
`ResearchProvider` interface separates live news/OSINT from financial calculations;
the default provider returns an explicit unavailable result and never invents news.

### Strategy agents

- **Growth:** evaluates the growth basket and requests deterministic comparison.
- **Dividend:** evaluates the dividend basket and requests deterministic comparison.
- **Momentum:** describes the transparent momentum mandate without forecasting.
- **Capital preservation:** focuses on volatility, drawdown, and defensive exposure.

Strategy agents return typed findings and requested operations; they cannot invoke
Bedrock or generate financial values.

### Governance

Governance is deterministic and runs after calculation. Current rules include:

- simulation-only enforcement;
- TFSA and RRSP scope limits;
- agreement or disagreement between volatility and drawdown evidence;
- historical return trade-off disclosure;
- Amira concentration control despite high risk tolerance;
- Mateo ESG evidence insufficiency and moderate-profile conflict;
- Robert short-horizon and capital-preservation conflict.

### Explainability

Amazon Bedrock receives only the verified question, conclusion, metrics, governance
findings, assumptions, limitations, and allowed evidence IDs. Its JSON response is
rejected if it lacks evidence, cites an unknown ID, or introduces a numeric claim.
All numbers shown to the user therefore originate in deterministic code.

## 4. Request and response contracts

The primary request includes:

- persona: `amira`, `mateo`, or `robert`;
- account: `TFSA` or `RRSP`;
- four strategy weights that sum to one;
- one source-to-destination strategy shift;
- CAD base currency;
- an explicit historical date window.

Validation rejects unknown strategies, missing weights, negative weights, totals
that do not equal one, impossible shifts, and invalid date order.

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

The currently deployed stack contains:

- private, encrypted, versioned S3 storage with blocked public access;
- ARM64 Python Lambda with bounded timeout, memory, and reserved concurrency;
- Lambda read-only access to the dataset bucket;
- a 14-day CloudWatch Logs group;
- one unnamed least-privilege Lambda execution role with S3 reads limited to the
  dataset prefix and CloudWatch writes limited to the function log group.

The locally validated, not-yet-deployed SAM update adds:

- a Standard Step Functions state machine with parallel account branches;
- constrained Bedrock agent, deterministic coordinator, and FastAPI Lambda functions;
- API Gateway HTTP API for the dashboard start/status contract;
- four additional unnamed least-privilege roles for the API, Step Functions,
  coordinator, and Bedrock agent runtime;
- three additional fourteen-day Lambda log groups.
- Cognito user pool, public PKCE client, managed-login domain, JWT authorizer, and
  API throttling.

The update also reconciles the exact deployed financial-tools dispatcher. The
market/headline operations—including the split `market_agent`, `classifier_agent`,
and `investor_position` contracts—all six dataset/model environment variables,
two-key scored-news write boundary, 120-second timeout, concurrency five, and
inference-profile permissions are preserved alongside the new investment
calculations.

The workshop configuration is fixed to `us-east-1` and the system-defined
`us.amazon.nova-lite-v1:0` profile. IAM must allow its profile ARN plus Nova Lite in
`us-east-1`, `us-east-2`, and `us-west-2`; organization controls must also permit
all three destinations. Read-only role inventory found no suitable existing
application execution role. IAM simulation confirms that the participant role can
create, configure, pass, and delete the unnamed roles in the template, so deployment
uses `CAPABILITY_IAM` and remains gated by change-set review and explicit approval.

The initial change set was reviewed and separately approved before execution. The
stack reached `CREATE_COMPLETE`; the six dataset files and manifest were uploaded
and independently verified against S3-reported SHA-256 checksums and version IDs.
The Lambda has no event source, resource policy, function URL, or async destination.
One separately approved live invocation read the expected S3 object versions and
matched every local metric and all 93 performance points exactly. Bedrock testing
remains separately approval-gated. Read-only inspection on 2026-11-15 confirmed
that the account currently has no PortfolioGuard state machine or HTTP API.

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
- all three persona governance boundaries;
- Bedrock evidence and numeric-claim rejection;
- allocation invariants, duplicate-date safeguards, and golden financial results;
- frontend lint and production build.
- AWS workflow-definition, named-agent capability, status-history, and local
  state-machine-equivalent tests.

The AWS acceptance test is opt-in and cannot pass through mocks. It must observe a
real Lambda request ID, versioned S3 sources, the configured Bedrock model ID, and a
grounded explanation.

## 10. Deferred work

After the real vertical slice is verified, planned work includes editable account
holdings, complete RRSP comparisons, VaR/CVaR, downside deviation, income analysis,
deeper momentum analytics, CloudWatch alarms/dashboard, prompt-injection tests,
and additional end-to-end persona scenarios.
