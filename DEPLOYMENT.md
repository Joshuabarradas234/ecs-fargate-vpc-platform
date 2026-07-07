# Deployment Guide

How to deploy this stack to a real AWS account, verify it works, and tear it
down cleanly. Read the whole thing before running anything — especially the
cost and teardown sections.

## Cost warning (read first)

Left running, this stack costs roughly **$80–100/month**: ALB (~$16), single
NAT gateway (~$32 + data), Fargate tasks (~$15), RDS db.t3.micro (~$15), plus
logs and data transfer. For a portfolio, the right pattern is
**deploy → verify → screenshot → destroy in one sitting**, which costs a few
dollars at most.

Before deploying, set a billing alarm so a forgotten stack can't cost you
$100. In the AWS console: Billing → Budgets → create a small budget with an
email alert.

## Prerequisites

- Terraform >= 1.5 and the AWS CLI, both configured (`aws sts get-caller-identity` works)
- Docker Desktop running (to build and push the image)
- An AWS account you're comfortable creating billable resources in

## Step 1 — validate locally (no cost)

```bash
cd terraform
terraform init
terraform fmt -check
terraform validate
```

Expect `Success! The configuration is valid.`

## Step 2 — plan against your account

```bash
terraform plan
```

Review what it will create: a VPC, subnets, NAT, ALB, ECS cluster/service,
RDS, IAM roles, Secrets Manager secret, KMS key, and CloudWatch alarms.
Nothing is created yet.

## Step 3 — apply

```bash
terraform apply
```

Type `yes`. This takes ~10–15 minutes, mostly RDS. When it finishes, note the
outputs — especially `alb_dns_name` and `ecr_repository_url`.

At this point the ECS service exists but its tasks will fail to start until an
image is in ECR (the task definition points at `:latest`, which doesn't exist
yet). That's expected — do step 4 next.

## Step 4 — build and push the image

```bash
# Authenticate Docker to your ECR registry (replace region/account as needed)
aws ecr get-login-password --region eu-west-2 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-2.amazonaws.com

# Build and push (use the ecr_repository_url output)
cd ../app
docker build -t <ecr_repository_url>:latest .
docker push <ecr_repository_url>:latest
```

Then force ECS to pull the new image:

```bash
aws ecs update-service \
  --cluster <ecs_cluster_name output> \
  --service <ecs_service_name output> \
  --force-new-deployment \
  --region eu-west-2
```

## Step 5 — verify it actually works (the milestone)

Wait 1–2 minutes for tasks to start and pass health checks, then:

```bash
curl http://<alb_dns_name>/health
# {"status":"ok"}

curl -X POST http://<alb_dns_name>/items \
  -H "Content-Type: application/json" -d '{"name":"first"}'
# {"id":1,"name":"first"}

curl http://<alb_dns_name>/items
# [{"id":1,"name":"first"}]
```

A `200` from `/health` through the ALB, and a POST/GET round-trip through
RDS, is the proof the whole path works: internet → ALB → ECS task → RDS.
Capture these for evidence.

## Step 6 — run the cost-audit tool against the live stack

```bash
cd ../cost-audit
pip install -r requirements.txt
python auditor.py --region eu-west-2
```

It will flag the NAT gateway (fixed cost), report the single-AZ RDS as
cost-optimised, and check tagging. This is the tool doing its job against real
resources.

## Step 7 — tear it down (do not skip)

```bash
cd ../terraform
terraform destroy
```

Type `yes`. Then confirm nothing lingers:

```bash
aws ecs list-clusters --region eu-west-2
aws rds describe-db-instances --region eu-west-2
```

RDS has `skip_final_snapshot = true` and `deletion_protection = false` so it
destroys cleanly. The ECR repo has `force_delete = true` so images don't block
teardown. If `destroy` ever stalls on the ECR repo or a stuck ENI, re-run it —
it's usually a timing issue that clears on a second pass.

## Optional — CI/CD deploy pipeline

`.github/workflows/deploy.yml` can do build/push/deploy automatically, but it
needs an OIDC role and repo variables set up first:

- An IAM role your GitHub repo can assume via OIDC, with ECR push + ECS update
  permissions
- Repo variables `AWS_REGION`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE`
- Secret `AWS_DEPLOY_ROLE_ARN`

Until those exist, `deploy.yml` only runs on manual dispatch or a `deploy-*`
tag, so it won't fail on normal commits. `ci.yml` (tests, validate, docker
build) needs none of this and runs on every push.
