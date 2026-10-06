# Collector on EC2 (M1)

Captures `station_status` every 2 min and `station_information` / `system_information`
daily, gzipped as served, into S3. Each run sends a `CaptureSuccess` heartbeat to
CloudWatch; an alarm emails you if captures stop.

Expected volume: ~720 captures/day, ~12 MB/day, ~360 MB/month.

Replace `YOUR-BUCKET`, `YOUR-REGION` and `you@example.com` below.

## 1. Bucket, role and alerting (once, from your laptop)

```sh
export AWS_REGION=YOUR-REGION BUCKET=YOUR-BUCKET

aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"   # omit this line in us-east-1
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Instance role: write-only to raw/ plus the heartbeat metric.
sed "s/YOUR-BUCKET/$BUCKET/" deploy/ec2/iam-policy.json > /tmp/ecobici-policy.json
aws iam create-role --role-name ecobici-collector --assume-role-policy-document \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam put-role-policy --role-name ecobici-collector --policy-name capture \
  --policy-document file:///tmp/ecobici-policy.json
aws iam create-instance-profile --instance-profile-name ecobici-collector
aws iam add-role-to-instance-profile --instance-profile-name ecobici-collector \
  --role-name ecobici-collector

# Email alert when station_status captures stop for 10 minutes.
TOPIC=$(aws sns create-topic --name ecobici-alerts --query TopicArn --output text)
aws sns subscribe --topic-arn "$TOPIC" --protocol email --notification-endpoint you@example.com
aws cloudwatch put-metric-alarm --alarm-name ecobici-capture-stopped \
  --namespace Ecobici --metric-name CaptureSuccess --dimensions Name=Feed,Value=station_status \
  --statistic Sum --period 600 --evaluation-periods 1 --threshold 1 \
  --comparison-operator LessThanThreshold --treat-missing-data breaching \
  --alarm-actions "$TOPIC" --ok-actions "$TOPIC"
```

Confirm the SNS subscription from the email AWS sends you.

## 2. Instance

Launch an Amazon Linux 2023 `t4g.nano` (arm64) with the `ecobici-collector` instance
profile, outbound internet, and SSH or SSM access. 8 GB of disk is plenty.

## 3. Install

```sh
# On the instance
sudo dnf install -y git
git clone https://github.com/David-Lazaro-Fernandez/ecobici-dock-availability-lgbm-v1.git
cd ecobici-dock-availability-lgbm-v1
sudo ./deploy/ec2/setup.sh          # first run stops and asks you to set the bucket
sudo sed -i "s#YOUR-BUCKET#$BUCKET#; s#us-east-1#$AWS_REGION#" /etc/ecobici/capture.env
sudo ./deploy/ec2/setup.sh
```

If the repo is private, copy it with `scp -r` or `rsync` instead of `git clone`.

## 4. Check it works

```sh
systemctl list-timers 'ecobici*'
journalctl -u 'ecobici-capture@station_status' -n 20
aws s3 ls "s3://$BUCKET/raw/station_status/" --recursive | tail
```

## 5. Three-day validation (V2, M1 exit criterion)

From your laptop after ~3 days:

```sh
aws s3 sync "s3://$BUCKET/raw/station_status" raw/station_status
uv run ecobici-capture-report raw/station_status
```

To pass: coverage above 99 %, no gap blocks rebuilding the label, and an understood
share of `stale` readings.

## Updating

```sh
cd ~/ecobici-dock-availability-lgbm-v1 && git pull && sudo ./deploy/ec2/setup.sh
```
