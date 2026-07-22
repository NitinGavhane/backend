#!/usr/bin/env bash
# One-command backend redeploy to AWS (build -> ECR -> EC2 restart).
# Run from the repo root or backend/:  bash backend/redeploy.sh
#
# Uses SSM Run Command, NOT SSH. Port 22 is closed on the security group --
# the SSH allowlist was a single home IP that broke every time the ISP rotated it.
# SSM commands run as root on the box, so no sudo is needed below.
set -euo pipefail

AWS="/c/Program Files/Amazon/AWSCLIV2/aws.exe"   # aws CLI is not on PATH in Git Bash
REGION="ap-south-1"
ACCOUNT="078525505229"
REG="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
IMG="$REG/garment-api:latest"
INSTANCE="i-0cb2f33a4ac2e3cee"
HEALTH_URL="http://3.6.231.38/health"             # Elastic IP (stable)

# Resolve backend dir regardless of where this is called from.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Building image..."
"$AWS" ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REG"
docker build --platform linux/amd64 -t "$IMG" "$DIR"

echo "==> Pushing to ECR..."
docker push "$IMG"

echo "==> Checking the instance is reachable via SSM..."
PING=$("$AWS" ssm describe-instance-information --region "$REGION" \
  --filters "Key=InstanceIds,Values=$INSTANCE" \
  --query "InstanceInformationList[0].PingStatus" --output text 2>/dev/null || true)
if [ "$PING" != "Online" ]; then
  echo "ERROR: instance $INSTANCE is not Online in SSM (got '${PING:-none}')."
  echo "       Check the SSM agent:  aws ssm start-session --target $INSTANCE"
  echo "       or the EC2 console (Session Manager / instance state)."
  exit 1
fi

echo "==> Restarting container on EC2 (via SSM)..."
# No 'docker login' here on purpose. /root/.docker/config.json registers
# docker-credential-ecr-login as a credHelper for this registry, so docker pulls ECR
# credentials from the garment-ec2-role instance profile on every pull and they never
# go stale. Adding an explicit login actually errors ("not implemented") because the
# ecr-login helper has no credential-store write support.
# --network garment-net is required: the database runs as the `garment-db`
# container on that user-defined network and is resolved by name from app.env
# (POSTGRES_HOST=garment-db). Dropping this flag breaks every DB query.
CMDS="commands=["
CMDS="$CMDS\"docker pull $IMG\","
CMDS="$CMDS\"docker network create garment-net 2>/dev/null || true\","
CMDS="$CMDS\"docker rm -f api 2>/dev/null || true\","
CMDS="$CMDS\"docker run -d --restart unless-stopped --network garment-net --env-file /home/ec2-user/app.env -p 127.0.0.1:8000:8000 --name api $IMG\""
CMDS="$CMDS]"

CMD_ID=$("$AWS" ssm send-command --region "$REGION" \
  --instance-ids "$INSTANCE" \
  --document-name "AWS-RunShellScript" \
  --comment "backend redeploy" \
  --parameters "$CMDS" \
  --query "Command.CommandId" --output text)
echo "    CommandId=$CMD_ID"

STATUS="Pending"
for i in $(seq 1 40); do
  STATUS=$("$AWS" ssm get-command-invocation --region "$REGION" \
    --command-id "$CMD_ID" --instance-id "$INSTANCE" \
    --query "Status" --output text 2>/dev/null || echo "Pending")
  case "$STATUS" in
    Success|Failed|Cancelled|TimedOut) break ;;
  esac
  sleep 5
done

echo "    Status=$STATUS"
"$AWS" ssm get-command-invocation --region "$REGION" \
  --command-id "$CMD_ID" --instance-id "$INSTANCE" \
  --query "StandardOutputContent" --output text | sed 's/^/    | /'

if [ "$STATUS" != "Success" ]; then
  echo "ERROR: remote restart did not succeed. stderr:"
  "$AWS" ssm get-command-invocation --region "$REGION" \
    --command-id "$CMD_ID" --instance-id "$INSTANCE" \
    --query "StandardErrorContent" --output text | sed 's/^/    ! /'
  exit 1
fi

echo "==> Waiting for health..."
for i in $(seq 1 15); do
  H=$(curl -s -m 15 "$HEALTH_URL" 2>/dev/null || true)
  if [ -n "$H" ]; then
    echo "OK: $H"
    exit 0
  fi
  sleep 8
done

echo "WARN: health check did not respond yet. Check container logs with:"
echo "  aws ssm send-command --region $REGION --instance-ids $INSTANCE \\"
echo "    --document-name AWS-RunShellScript --parameters 'commands=[\"docker logs --tail 50 api\"]'"
exit 1
