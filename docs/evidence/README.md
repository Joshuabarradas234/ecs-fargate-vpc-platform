# Live deployment evidence

Screenshots from deploying this repo's Terraform to a real AWS account
(eu-west-2) on 7 July 2026, verifying the running stack, then destroying it
with `terraform destroy`. The stack is not left running — these are captured
from a deploy-verify-destroy cycle.

## 01 — API live through the ALB, round-trip to RDS

`01-api-live-health-and-items.png`

Shows, against the live Application Load Balancer DNS name:

- the ECS service healthy (`running: 3, desired: 2, pending: 0, failed: null`)
- `GET /health` returning `{"status": "ok"}`
- `POST /items` creating a record (`id: 1, name: first`)
- `GET /items` reading it back

This proves the full request path works end to end: internet -> ALB ->
Fargate task (private subnet) -> RDS PostgreSQL (private subnet) -> back.

## 02 — Cost-audit tool against live infrastructure

`02-cost-audit-live-run.png`

Shows `python auditor.py --region eu-west-2` run against the live account,
correctly:

- flagging the NAT gateway at ~$32.40/month (the stack's main cost driver)
- reporting the RDS instance as `single-AZ (cost-optimised)`, class db.t3.micro
- printing an estimated addressable monthly cost, with the caveat that the
  figures are estimates for prioritisation, not a billing statement

This demonstrates the read-only auditor working against real resources, not
just its unit tests.

## Teardown

After capturing evidence, `terraform destroy` removed all 50 resources.
Confirmed empty afterwards: `aws ecs list-clusters`, `describe-db-instances`,
and `describe-nat-gateways` all returned no resources — nothing left billing.
