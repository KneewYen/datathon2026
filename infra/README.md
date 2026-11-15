# AWS infrastructure

`template.yaml` defines the proposed AWS-owned PortfolioGuard AI vertical slice for
the Polyfinances Workshop Studio account in `us-east-1`:

- Private, encrypted, versioned S3 data bucket
- Standard Step Functions workflow with parallel TFSA/RRSP branches
- Named Nova Lite orchestrator, account, strategy, and explainability agents
- Deterministic financial-tools and coordinator Lambdas
- FastAPI Lambda behind API Gateway HTTP API for start/status polling
- Fourteen-day Lambda log retention in CloudWatch Logs
- CloudFormation-generated, least-privilege roles scoped to their exact functions,
  workflow, dataset prefix, log groups, inference profile, and destination models

The template hosts FastAPI but not the Next.js frontend. The dashboard may run
locally with `NEXT_PUBLIC_API_URL` set to the `BackendApiUrl` stack output. Local
FastAPI remains available with `ORCHESTRATION_MODE=local` for development.

## Deployment status and next gate

The exact first change set was approved and reached `CREATE_COMPLETE` on
2026-11-14 with only S3, financial Lambda, its role, and its log group. The
Step Functions/API/agent expansion is locally validated but not deployed. Before
updating the stack, create a no-execute change set, inspect every action and policy,
and obtain explicit approval. The remaining approval gates are:

1. No-execute change-set creation and review
2. Change-set execution
3. One bounded end-to-end Step Functions/Nova/Lambda acceptance run
4. Any dataset replacement, additional invocation, or cleanup

Read-only inspection found no suitable existing application execution role. IAM
simulation confirms that `WSParticipantRole` may create, configure, pass, and later
delete the unnamed roles in this template. Deployment therefore requires
`CAPABILITY_IAM`; it still requires explicit user approval and change-set review.

No temporary credential values belong in `.env` files. Configure the Workshop
Studio credentials locally using the standard AWS credential chain and expose only
the named profile to the application.

See `docs/AWS_DEPLOYMENT_GATE.md` for the readiness checklist, complete resource
inventory, IAM requirements, cost estimate, approvals, and cleanup plan.
