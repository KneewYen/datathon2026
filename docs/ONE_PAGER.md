# PortfolioGuard AI: one-page summary

## The problem

Investment tools tend to agree with the investor. A 59-year-old who reads about a
hot stock gets a buy button, not a conversation about his horizon. Generative AI
makes this worse when it invents figures or hides how an answer was produced.

## The solution: an advisor that knows when to say no

PortfolioGuard AI is a multi-agent decision-support prototype for fictional TFSA and
RRSP portfolios. It does two things for each of the case personas:

1. **Persona scenario.** Each persona gets a scenario built around what the brief
   says they test. Amira diversifies away from tech, Mateo moves into ESG, and Robert
   considers adding growth before retirement. The answers differ because the
   evidence differs.
2. **Suitability challenge.** The investor asks for something specific ("Put 25% of
   my RRSP in NVDA"). The system measures the request as asked, a capped version, and
   a diversified alternative on the same AWS data. It applies the persona's risk
   budget and returns a verdict: *aligned*, *cap*, *alternative* or *conflict*.

The same NVDA request is capped for Robert because a 2022 replay loses -22.4% against
his -15% loss budget. Amira is capped at a 15% total position, and her Tesla request
is allowed as asked. The adaptation is the product.

## Why it is agentic

```text
Global Orchestrator
  ├─ Account agent → only the strategy agents affected by the change
  ├─ Request parser (deterministic) → Suitability Challenge Agent
  ├─ AWS Lambda financial tools (compare_strategy_shift, compare_scenarios)
  ├─ Governance Agent (persona risk budget)
  └─ Explainability Agent → Amazon Bedrock
```

Every step is typed, recorded and shown in the dashboard trace. No agent appears in
a trace unless it ran.

## Why the result is trustworthy

- **Numbers come from Lambda.** Bedrock writes digit-free prose. Code appends every
  figure from the Lambda evidence registry, and each number in the answer is a
  button showing its evidence ID, raw value, formula version and S3 object version.
- **Stress replay.** Every proposal is replayed through 2022, when stocks and bonds
  fell together, and timed to full recovery against the persona's horizon.
- **Robustness badge.** Each conclusion is re-tested on the full five-year history.
  It is marked *Robust* or *Window-sensitive*.
- **Data-grounded governance.** Loss budget, recovery-time limit, single-company cap,
  crypto cap and an ESG sector screen use `assets_universe.csv` sectors. Missing
  company-level ESG controversy data is disclosed, not invented.
- **Validated explanations.** Explanations are rejected and retried if they contain
  digits, cite unknown evidence, or use forecast-like wording about returns.

## AWS contribution

- **Amazon S3:** private, encrypted, versioned data with checksums verified against
  a manifest on every call.
- **AWS Lambda:** all calculations, including the 2022 replay, recovery timing and
  multi-scenario comparison on one calendar.
- **Amazon Bedrock (Nova Lite):** grounded, validated explanation.
- **IAM and CloudWatch:** least privilege and correlated structured logs.

## User value

An investor sees what they asked for, what fits, and why, in dollars on their
fictional balance and in months to recover. Every figure can be verified.
Simulation only. Not financial advice. No real trades.