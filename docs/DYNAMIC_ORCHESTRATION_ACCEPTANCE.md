# Dynamic multi-agent orchestration acceptance gate

Status as of 2026-11-15: source implementation and local validation complete; live
AWS deployment and execution are intentionally not verified because they require
separate approval.

## Execution contract

1. Deterministic preparation establishes the user-authorized candidate account
   scope.
2. The Global AI Orchestrator selects account-agent names with Nova Lite. The
   global routing gate rejects out-of-scope names and turns only selected or
   explicitly policy-required accounts into Step Functions Map items.
3. Each selected Account AI Orchestrator selects only specialists from its static
   account allowlist. The account routing gate produces specialist Map items and
   injects a permitted specialist only when required exposure or purchase-risk
   evidence would otherwise be absent.
4. Each invoked specialist selects only tools from its static allowlist. The tool
   routing gate produces tool Map items. A fixed Choice maps the four supported
   operations to fixed Lambda resources; no model output can become a resource ARN.
5. The financial Lambda independently checks the routed specialist/operation pair.
6. Account synthesis uses only completed routed results. Global governance and the
   final Nova explanation receive only validated evidence and explicit limitations.

## Acceptance matrix

| # | Result | Evidence |
| --- | --- | --- |
| 1 | PASS | `validate_global_route`; global-selection and question-scope tests |
| 2 | PASS | `validate_account_route`; selected-versus-policy specialist tests |
| 3 | PASS | `validate_strategy_route`; selected, skipped, and mandatory-tool tests |
| 4 | PASS | Nested Maps and fixed Choice in `investment_analysis.asl.json`; definition test and AWS definition validator |
| 5 | PASS | Required-operation policy, partial synthesis, evidence-ID reconciliation, and failure tests |
| 6 | PASS | `DelegationRecord`, routing/synthesis records, and completed-workflow test |
| 7 | PASS | Dashboard `DelegationLedger` renders returned records and `ExecutionTrace` renders emitted events |
| 8 | PASS | Routing tests cover divergent questions/selections, non-invocation, unauthorized output, mandatory policy, and partial failure |
| 9 | PASS | Agent-runtime parent/stage checks, fixed Step Functions dispatch, financial-Lambda authorization, scoped workflow IAM |
| 10 | PASS | Cognito/PKCE, throttling, legacy financial operations, environment, timeout, concurrency, S3, and IAM configuration are preserved |

`PASS` means the criterion is implemented and covered by source-level or local
integration verification. It does not claim that the new workflow has run in AWS.

## Verification summary

- Backend test suite: pass, with the separately gated live-AWS test skipped.
- Financial Lambda compatibility/calculation suite: pass.
- Frontend tests, ESLint, TypeScript, and Next.js production build: pass.
- SAM lint, full SAM build, built-template lint, CloudFormation `ValidateTemplate`,
  and Step Functions definition validation: pass.
- Repository secret scan: pass.
- No CloudFormation change set, deployment upload, resource mutation, or live
  Lambda, Bedrock, or Step Functions invocation was performed.

## Remaining approval gate

The current source is ready for a separately authorized replacement
`sam deploy --no-execute-changeset` review. The existing superseded change set must
not be executed. Deployment and live end-to-end verification remain unverified
until separately approved.
