# AWS infrastructure

`template.yaml` defines the deployed first PortfolioGuard AI vertical slice for the
Polyfinances Workshop Studio account in `us-east-1`:

- Private, encrypted, versioned S3 data bucket
- Deterministic Python Lambda with read-only access to the data bucket
- Fourteen-day Lambda log retention in CloudWatch Logs
- One unnamed, least-privilege Lambda execution role scoped to the dataset prefix
  and function log group
- Review-only least-privilege policy documents for US Nova Lite caller access

The template does not host the frontend or FastAPI service. During the first slice,
the local FastAPI backend uses Workshop Studio temporary credentials to call the
deployed Lambda and `us.amazon.nova-lite-v1:0`.

## Deployment status and next gate

The exact reviewed change set was approved and reached `CREATE_COMPLETE` on
2026-11-14. Before any subsequent update, repeat change-set review and obtain user
approval. The remaining approval gates are:

1. A bounded Bedrock Nova Lite acceptance invocation
2. Any additional Lambda invocation
3. Any dataset replacement, CloudFormation update, or cleanup

Read-only inspection found no suitable existing application execution role. IAM
simulation confirms that `WSParticipantRole` may create, configure, pass, and later
delete the unnamed role in this template. Deployment therefore requires
`CAPABILITY_IAM`; it still requires explicit user approval and change-set review.

No temporary credential values belong in `.env` files. Configure the Workshop
Studio credentials locally using the standard AWS credential chain and expose only
the named profile to the application.

See `docs/AWS_DEPLOYMENT_GATE.md` for the readiness checklist, complete resource
inventory, IAM requirements, cost estimate, approvals, and cleanup plan.
