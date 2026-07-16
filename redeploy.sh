#!/usr/bin/env bash
# One-command backend redeploy to AWS (build -> ECR -> EC2 restart).
# Run from the repo root or backend/:  bash backend/redeploy.sh
set -euo pipefail

AWS="/c/Program Files/Amazon/AWSCLIV2/aws.exe"   # aws CLI is not on PATH in Git Bash
REGION="ap-south-1"
ACCOUNT="078525505229"
REG="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
IMG="$REG/garment-api:latest"
EC2_HOST="ec2-user@3.6.231.38"                    # Elastic IP (stable)
KEY="/c/Users/gavha/.ssh/garment-key.pem"
SSHO="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"

# Resolve backend dir regardless of where this is called from.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Building image..."
"$AWS" ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REG"
docker build --platform linux/amd64 -t "$IMG" "$DIR"

echo "==> Pushing to ECR..."
docker push "$IMG"

echo "==> Restarting container on EC2..."
ssh $SSHO -i "$KEY" "$EC2_HOST" "bash -s" <<REMOTE
set -e
sudo docker pull "$IMG"
sudo docker rm -f api 2>/dev/null || true
sudo docker run -d --restart unless-stopped --env-file /home/ec2-user/app.env -p 80:8000 --name api "$IMG"
REMOTE

echo "==> Waiting for health..."
for i in \$(seq 1 15); do
  H=\$(curl -s -m 15 http://3.6.231.38/health 2>/dev/null || true)
  [ -n "\$H" ] && { echo "OK: \$H"; exit 0; }
  sleep 8
done
echo "WARN: health check did not respond yet; check 'sudo docker logs api' on the box."
