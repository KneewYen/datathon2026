# PortfolioGuard AI — one-page summary

## The problem

Portfolio decisions are often presented as a single recommendation without showing
how the answer was produced, which evidence supports it, or which trade-offs and
limitations matter. Generative AI can make this worse if it invents financial
figures or hides the calculation path.

## The solution

PortfolioGuard AI is a transparent multi-agent decision-support prototype for
fictional TFSA and RRSP portfolios. A user asks a hypothetical allocation question;
the system delegates it through account and strategy agents, calculates historical
risk in AWS, applies governance rules, and uses Amazon Bedrock only to explain
verified evidence.

The flagship scenario asks:

> I am considering buying $5,000 CAD of NVIDIA. Which account is a better fit, my TFSA or RRSP?

## Why it is agentic

```text
Global Orchestrator
  → TFSA and RRSP Account Agents
    → Growth / Momentum and Dividend / Preservation Agents
      → deterministic AWS Lambda financial tool
  → Governance Agent
  → Bedrock Explainability Agent
```

Every delegation is typed, recorded, visible in the dashboard, and covered by
tests. Agents that do not contribute to a request are not invoked.

## Why the result is trustworthy

- Lambda is the only source of financial metrics.
- Lambda verifies manifest checksums, reads versioned S3 data, and returns object
  provenance.
- Adjusted close, CAD currency conversion, common calendars, and rebalance policy
  are explicit.
- Bedrock may cite only supplied evidence IDs and cannot introduce numbers.
- Governance exposes persona conflicts, account-scope limits, and missing ESG data.
- Historical observations are clearly separated from future outcomes.
- The application cannot execute a trade.

## Primary decision support

The system discovers existing direct NVIDIA holdings and covered QQQ/SPY overlap
before simulating the purchase in each populated account. It compares account cash,
company exposure, historical volatility, drawdown, concentration, objectives, and
risk limits. If TFSA and RRSP agents disagree, governance preserves the conflict
instead of forcing one recommendation.

## AWS contribution

- **Amazon S3:** encrypted, private, versioned source data.
- **AWS Lambda:** deterministic financial calculations.
- **AWS Step Functions:** durable hierarchy, parallel account analysis, and an
  execution history shown live in the dashboard.
- **Amazon Bedrock:** grounded explanation through the Converse API.
- **IAM:** least-privilege access to the function and selected model resources.
- **CloudWatch:** correlated structured execution logs.

## User experience

The Next.js dashboard shows the investor persona, current and proposed allocation,
risk metrics, performance comparison, agent delegation trace, governance controls,
assumptions, limitations, and exact source objects. If AWS is unavailable, it shows
an honest unavailable state instead of placeholder results.

## Status and next step

The cross-account slice, AWS state machine, named Nova agents, API polling, tests,
and dashboard are implemented and locally validated. Core AWS infrastructure and
the earlier strategy-shift Lambda were previously verified, but the workflow update
is not deployed. The next separately gated step is creating and reviewing a
no-execute CloudFormation change set. Execution and the first bounded live workflow
remain separate approvals. Bedrock has not yet been invoked.
