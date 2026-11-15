# PortfolioGuard AI five-minute demo script

## Before recording

- Confirm the live AWS integration test passes against the approved stack.
- Confirm the backend health endpoint and live integration test report the expected
  Region, Lambda, versioned S3 sources, and Bedrock model.
- Use the versioned fictional Jordan Lee accounts only.
- Open CloudWatch Logs to the current Lambda log group in a separate tab.
- Keep a prior real-run response available only as a clearly labeled backup artifact.

## 0:00–0:35 — Problem and promise

**Say:**

“Portfolio changes are often delivered as a recommendation without a transparent
calculation path. PortfolioGuard AI turns a hypothetical question into a traceable,
source-backed comparison. It never executes a trade, and every portfolio shown is
fictional.”

Show the landing page and simulation-only boundary.

## 0:35–1:05 — Portfolio context and question

**Say:**

“Our question is deliberately concrete: Jordan is considering a five-thousand-dollar
Canadian purchase of NVIDIA. Which populated account is a better fit—the growth
TFSA or the retirement RRSP? Both accounts and every holding are fictional.”

Point to the question input and open the workspace. Do not describe the result yet.

## 1:05–1:45 — Real agent hierarchy

Click **Analyze purchase**.

**Say while it runs:**

“This is not one prompt pretending to be many agents. The global orchestrator
activates both account agents. TFSA delegates to growth and momentum; RRSP delegates
to dividend and capital preservation. They request typed exposure, market, research,
and purchase-simulation tools. Shared work is cached, but every delegated use remains
visible.”

When the result appears, scroll to **Actual execution trace** and point out parent
indentation, completed versus blocked status, evidence IDs, governance, and Bedrock.

## 1:45–2:40 — Deterministic AWS evidence

Scroll to **Account comparison**.

**Say:**

“AWS Lambda reads prices and USD/CAD observations from private, versioned Amazon S3
objects. Before simulating a purchase, it values direct NVIDIA holdings and the
covered NVIDIA weight inside QQQ and SPY using a reviewed issuer fixture.”

“It then simulates the same cash purchase independently in each account and compares
the before-and-after NVIDIA exposure, volatility, maximum drawdown, concentration,
and cash balance. The price is the latest dataset close, not a real-time quote.”

Point to the existing direct and ETF exposure summary, then the two account cards.

## 2:40–3:20 — Conflict, not recommendation

**Say:**

“The agents are allowed to disagree. The TFSA has an aggressive long horizon; the
RRSP has a conservative retirement objective and a larger cash floor. Governance
preserves those account-specific conflicts instead of averaging them into a false
single recommendation.”

Open **Assumptions and limitations**. Mention fractional shares, historical risk,
fees, taxes, contribution room, ETF staleness, and fictional holdings.

## 3:20–4:05 — Grounded Bedrock explanation and governance

**Say:**

“Only Lambda can generate financial values. Bedrock receives a closed evidence
packet and explains the result in words. Its response fails validation if it cites
an unknown evidence ID or tries to introduce a number.”

Point to the research status and governance findings.

**Say:**

“No approved live news provider is configured, so the research agent reports that
gap and the final answer is forbidden from making recent-news claims. Missing data
is visible; it is never filled with invented headlines.”

## 4:05–4:35 — Prove the AWS path

Open CloudWatch Logs.

**Say:**

“Here is the same analysis ID and AWS Lambda request ID in CloudWatch. The S3 source
list in the response includes version IDs or ETags, so this result is reproducible.
IAM limits the backend to this function and the approved Bedrock resources.”

Show one `calculation_started` and matching `calculation_completed` structured log.
Do not expose account identifiers or credentials.

## 4:35–5:00 — Close

Return to the answer.

**Say:**

“PortfolioGuard AI demonstrates a safer pattern for agentic financial decision
support: purposeful delegation, deterministic cloud tools, visible disagreement,
and language generation constrained by evidence. The user sees which account better
matches the fictional objective, the trade-offs, and exactly how the answer was built.”

## Failure recovery

If AWS fails during the live demo, keep the honest error state visible and explain
that local placeholders are intentionally disabled. Then show a timestamped prior
response that is clearly labeled as a previous real AWS run, followed by its
matching CloudWatch entries. Never present a fixture or mocked response as live.
