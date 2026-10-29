# StoreOps Deployment

This guide describes how StoreOps is built and run with Docker locally and deployed
to AWS ECS Fargate from GitHub Actions.

## Prerequisites

- Docker Engine or Docker Desktop
- Git
- An AWS account with:
  - an Amazon ECR repository named `storeops-repository`
  - an ECS Fargate cluster named `ambitious-wolf-thfgx9`
  - an ECS service named `storeops-taskdefinition-service`
  - a task definition family named `storeops-taskdefinition`
  - an ECS task execution role
- GitHub repository secrets:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`

The AWS resources are used by the repository in its current configuration. If resource
names or the AWS account differ, update [.github/workflows/deploy.yml](.github/workflows/deploy.yml)
and [.aws/task-definition.json](.aws/task-definition.json) before deploying.

## Application build

The [Dockerfile](Dockerfile) uses Python 3.12 and installs the project package with:

```dockerfile
pip install --no-cache-dir .
```

The container starts StoreOps with:

```text
uvicorn storeops.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

`PORT` defaults to `8080`; the exposed container port is also `8080`.

## Local Docker deployment

Run all commands from the repository root.

### Build the image

```bash
docker build -t storeops:local .
```

### Run the container

```bash
docker run --rm --name storeops \
  --publish 8080:8080 \
  --env PORT=8080 \
  storeops:local
```

The API will be available on `http://localhost:8080`.

To run in the background:

```bash
docker run -d --name storeops \
  --publish 8080:8080 \
  --env PORT=8080 \
  storeops:local
```

Useful container commands:

```bash
docker logs --follow storeops
docker ps
docker stop storeops
docker rm storeops
```

### Verify the local deployment

```bash
curl --fail http://localhost:8080/health/live
curl --fail http://localhost:8080/health/ready
```

The expected responses are:

```json
{"status":"alive"}
```

```json
{"status":"ready"}
```

The API documentation is available at:

- `http://localhost:8080/docs`
- `http://localhost:8080/redoc`

The health endpoints are public and do not require StoreOps identity headers.

## AWS ECS deployment

AWS deployment is automated by
[.github/workflows/deploy.yml](.github/workflows/deploy.yml).

The workflow runs when a commit is pushed to the `master` branch. It does not deploy
for pushes to feature branches, pull requests, or tags.

### ECS configuration

[.aws/task-definition.json](.aws/task-definition.json) defines:

- task family: `storeops-taskdefinition`
- launch type: AWS Fargate
- CPU: `256`
- memory: `512`
- network mode: `awsvpc`
- container name: `storeops`
- container port: `8080`
- host port: `8080`
- execution role:
  `arn:aws:iam::325212745596:role/ecsTaskExecutionRole`
- log group: `/ecs/storeops-taskdefinition`
- log region: `us-east-1`
- CPU architecture: `X86_64`
- operating system: Linux

The task definition contains an existing ECR image digest. GitHub Actions replaces
the image with the newly built image digest before deployment.

### Credentials

The workflow name is configured for AWS credentials with:

```yaml
aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
aws-region: us-east-1
```

Despite the workflow's `id-token: write` permission, the current steps use repository
secrets for IAM credentials rather than an OIDC role-to-session configuration. Configure
both repository secrets with credentials that can log in to ECR and register and deploy
ECS task definitions.

### Automatic deployment from GitHub

From a local clone:

```bash
git switch master
git pull --ff-only origin master
git push origin master
```

Alternatively, merge or fast-forward a feature branch into `master`, then push:

```bash
git switch master
git merge --ff-only <feature-branch>
git push origin master
```

The push triggers the `Build and deploy StoreOps to ECS` workflow.

### Workflow sequence

1. GitHub checks out the pushed commit.
2. GitHub Actions configures AWS credentials in the `us-east-1` region.
3. The workflow authenticates Docker to the AWS ECR registry.
4. Docker builds the repository root image and tags it with the Git commit SHA.
5. The image is pushed to the `storeops-repository` ECR repository.
6. The workflow renders a new ECS task definition by replacing the `storeops` image in
   `.aws/task-definition.json`.
7. The new task definition is registered with ECS.
8. ECS service `storeops-taskdefinition-service` on cluster
   `ambitious-wolf-thfgx9` is updated with the new task definition.
9. GitHub Actions waits for ECS service stability.

The image address generated during deployment has this form:

```text
<account>.dkr.ecr.us-east-1.amazonaws.com/storeops-repository:<git-sha>
```

## Verify an ECS deployment

Monitor the GitHub Actions run for the workflow name
`Build and deploy StoreOps to ECS`. A successful run means the ECS deployment action
completed and the service became stable.

Verify the service from the AWS CLI:

```bash
aws ecs describe-services \
  --cluster ambitious-wolf-thfgx9 \
  --services storeops-taskdefinition-service \
  --region us-east-1
```

Verify the running task definition:

```bash
aws ecs describe-services \
  --cluster ambitious-wolf-thfgx9 \
  --services storeops-taskdefinition-service \
  --region us-east-1 \
  --query 'services[0].{status:status,taskDefinition:taskDefinition,running:runningCount,pending:pendingCount,desired:desiredCount}'
```

View container logs:

```bash
aws logs tail /ecs/storeops-taskdefinition \
  --follow \
  --region us-east-1
```

## Health checks

The application provides:

- `GET /health/live` for process liveness
- `GET /health/ready` for application readiness

In the current repository configuration, `.aws/task-definition.json` does not contain
an ECS container `healthCheck`, the workflow does not create one, and Docker has no
Dockerfile `HEALTHCHECK` instruction. No load-balancer target-group configuration is
managed by the workflow. Do not assume ECS or Docker is currently calling the health
endpoints until infrastructure is explicitly configured for them.

## Rollback

To deploy an earlier image through GitHub Actions, revert or restore the desired code
commit and push the result to `master`. The workflow creates a new task definition using
the earlier commit SHA as the ECR image tag.

For a direct ECS rollback, use the AWS Console or CLI to select a previous registered
task-definition revision that is compatible with the ECS service:

```bash
aws ecs list-task-definitions \
  --family-prefix storeops-taskdefinition \
  --sort DESC \
  --region us-east-1
```

Then update the service with the chosen revision:

```bash
aws ecs update-service \
  --cluster ambitious-wolf-thfgx9 \
  --service storeops-taskdefinition-service \
  --task-definition storeops-taskdefinition:<revision> \
  --region us-east-1
```

## Troubleshooting

### ECS service will not become stable

Check:

- ECS events in `describe-services`
- stopped task reasons
- CloudWatch logs in `/ecs/storeops-taskdefinition`
- port mapping for container port and host port `8080`
- availability of the ECS task execution role
- whether the service can pull the image digest from ECR

### Workflow cannot authenticate to AWS

Verify that `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are repository secrets and
that the credentials permit ECR login, ECS service updates, ECS task-definition
registration, and CloudWatch logging operations required by the deployment.

### Container exits immediately

Run the image locally and inspect the logs:

```bash
docker run --rm --publish 8080:8080 storeops:local
docker logs storeops
```

Also verify that `pip install --no-cache-dir .` created an installable `storeops` package
and that `storeops.main:app` is importable.
