# PortfolioGuard AI

**Team 62 · AlphaForge AI Datathon 2026**

PortfolioGuard AI is an evidence-backed decision-support prototype for fictional
TFSA and RRSP portfolios. It is **an advisor that knows when to say no**: each case
persona gets a scenario built around what the brief says they test, and a
suitability challenge lets them ask for something specific ("Put 25% of my RRSP in
NVDA"). The system measures the request as asked, capped, and as a diversified
alternative in AWS Lambda, replays the 2022 stock-and-bond selloff, applies the
persona's risk budget, and returns a verdict. Bedrock writes the explanation. Every
number in it is inserted by code from Lambda evidence and can be clicked to see its
source.

> Simulation only. Fictional portfolios. Not financial advice. No real trades.

## What the jury will see

| Request | Amira (high risk, 15+ yrs) | Robert (low–moderate, 3–5 yrs) |
| --- | --- | --- |
| "Put 25% in NVDA" | **cap**: 32.5% NVDA total exceeds her 15% single-company cap | **cap**: 2022 replay -22.4% (-$100,981) vs -15% budget; 5% fits (-11.2%) |
| "Should I buy Tesla?" | **aligned**: within budget | **cap**: 10% exceeds the 5% cap |
| "Add bitcoin" | **alternative**: no crypto room above 10% | **alternative**: crypto is outside his profile |

Mateo's "Put 10% in Exxon" is screened out by sector (`assets_universe.csv`), so the
system recommends the ESG basket. It also discloses that the ESG basket fell more in
2022.

The original golden scenario is still the default `POST /api/analysis` request:
moving 20% of a TFSA from growth to dividend. Annualized volatility falls from 18.48%
to 13.71%, maximum drawdown improves from -19.72% to -15.53%, and historical return
falls from 30.80% to 27.42% (2023-11-13 to 2026-11-12). These are observations, not
forecasts.

## Architecture

```text
Next.js dashboard → FastAPI → Global Orchestrator
   ├─ Persona scenario: Account Agent → affected Strategy Agents
   │     → Lambda compare_strategy_shift (+ 2022 replay, recovery, robustness)
   ├─ Suitability challenge: Request parser → Suitability Challenge Agent
   │     → Lambda compare_scenarios (requested / capped / alternative)
   ├─ Governance Agent (account scope + persona risk budget, ESG sector screen)
   └─ Explainability Agent → Amazon Bedrock (digit-free prose)
         + code-inserted verified figures from the Lambda evidence registry

Lambda reads versioned Amazon S3 data and verifies manifest checksums on every call;
CloudWatch receives correlated structured logs.
```

## Current status

- Deployed in `us-east-1`: private versioned S3 dataset, deterministic Lambda
  (updated with `compare_scenarios`, stress replay and robustness), least-privilege
  role, and CloudWatch log group.
- Persona scenarios and the suitability challenge run end to end against the live
  Lambda and Amazon Bedrock Nova Lite.
- Backend: 37 tests. Lambda: 7 tests. Frontend lint and type-check are clean.
- Deferred: VaR/CVaR, company-level ESG controversy data, macro publication-date
  handling, and hosting the API on AWS.

Project documentation:

- [Living implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md)
- [One-page summary](docs/ONE_PAGER.md)
- [Five-minute demo script](docs/DEMO_SCRIPT.md)
- [AWS deployment approval gate](docs/AWS_DEPLOYMENT_GATE.md)

## Local development

Prerequisites: Python 3.12+, Node.js 22+, and npm.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest -m "not integration" -q
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

The API runs at `http://localhost:8000`; the landing page runs at
`http://localhost:3000`, and the demo workspace is at
`http://localhost:3000/dashboard`. Selecting a persona on the landing page and
choosing **Analyze with live AWS** opens the workspace and runs that persona's
scenario. The **Suitability challenge** panel below it runs specific requests. The
workspace deliberately shows no substitute metrics when live AWS is unavailable.

On Windows PowerShell, activate the backend with `.\.venv\Scripts\Activate.ps1` and
use `Copy-Item` instead of `cp`.

Main endpoints: `POST /api/analysis/persona/{amira|mateo|robert}`,
`POST /api/challenge` (`{"persona_id": "robert", "message": "Put 25% of my RRSP in NVDA"}`),
`POST /api/analysis` (custom scenario), and `GET /api/meta`.

To deploy Lambda code changes without SAM, zip `handler.py`, `calculations.py`,
`data_access.py` and `__init__.py` from `lambda/financial_tools/` and run
`aws lambda update-function-code --function-name portfolioguard-workshop-financial-tools --zip-file fileb://financial_tools.zip`.

FastAPI loads `backend/.env` for local development without overriding variables
already supplied by the shell or deployment environment.

## Environment configuration

Backend configuration is documented in `backend/.env.example`:

| Variable | Workshop value | Purpose |
| --- | --- | --- |
| `AWS_REGION` | `us-east-1` | Lambda, S3, and Bedrock source Region |
| `AWS_PROFILE` | `portfolioguard-workshop` | Local AWS named profile using temporary Workshop Studio credentials |
| `BEDROCK_MODEL_ID` | `us.amazon.nova-lite-v1:0` | Amazon Nova Lite US inference profile |
| `LAMBDA_FUNCTION_NAME` | `portfolioguard-workshop-financial-tools` | Deterministic calculation function |
| `S3_BUCKET` | CloudFormation `DataBucketName` output | Versioned dataset bucket used by deployment helpers |
| `DATA_PREFIX` | `starter/v1` | Approved dataset prefix reported by the readiness endpoint |
| `FRONTEND_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed to call FastAPI |

The frontend uses one API base URL, `NEXT_PUBLIC_API_URL`, defaulting to
`http://localhost:8000` in `frontend/.env.example`. The app workspace uses that
same connection for readiness, conversational actions, accounts, Lambda-backed
analysis, and Bedrock-backed explanations. Keep `.env` and `.env.local` files outside Git. Never place
temporary access keys or session tokens in environment example files; configure the
named profile using Workshop Studio's secure temporary-credential workflow.

## Verification

```bash
cd backend && .venv/bin/pytest -m "not integration" -q
python3 -m unittest discover -s lambda/tests -v
cd frontend && npm run lint && npm run build
cd .. && SAM_CLI_TELEMETRY=0 sam validate --lint --template-file infra/template.yaml
```

After an approved AWS deployment, run the opt-in acceptance test with a secure AWS
profile and the deployed outputs:

```bash
cd backend
RUN_AWS_INTEGRATION=1 \
AWS_PROFILE=portfolioguard-workshop \
AWS_REGION=us-east-1 \
LAMBDA_FUNCTION_NAME=portfolioguard-workshop-financial-tools \
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 \
.venv/bin/pytest -m integration -q
```

## Data controls

- Returns use adjusted close.
- USD listings convert to CAD using the latest USD/CAD observation on or before
  each asset date.
- The portfolio calendar is the intersection of every holding's available dates.
- The initial comparison uses constant weights with daily rebalancing.
- Lambda verifies the S3 dataset ID, prefix, file sizes, and SHA-256 checksums
  against the committed manifest before calculating.
- S3 object version IDs or ETags are returned as metric provenance.
- Duplicate dates, non-positive prices/FX, missing assets, insufficient common
  history, invalid weights, and impossible shifts fail closed.
- Macro reference dates are not used in backtests until publication-date handling
  is available.

The immutable local manifest is
[data/manifests/starter-v1.json](data/manifests/starter-v1.json).

## Repository map

- `frontend/` — Next.js dashboard
- `backend/` — FastAPI, hierarchy, governance, and Bedrock client
- `lambda/financial_tools/` — deterministic S3-backed calculations
- `infra/template.yaml` — deployed AWS SAM/CloudFormation template
- `scripts/` — manifest and S3 upload helpers
- `docs/` — plan, technical documentation, one-pager, demo script, and decisions
- `hackathon_info/` — challenge documents and reviewed starter dataset

The original project Wiki remains available for historical context, while the
in-repository plan is authoritative for the approved implementation architecture.
