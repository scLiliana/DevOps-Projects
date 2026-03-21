#!/bin/bash
# configure_base.sh
# Este archivo se copia a la instancia y se ejecuta remotamente

set -euxo pipefail
exec > >(tee -a /var/log/golden-ami-setup.log) 2>&1
echo "=== START: $(date) ==="

# ── 1. AWS CLI ────────────────────────────────────────────────────────────────
echo ">>> Verificando AWS CLI..."
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    unzip /tmp/awscliv2.zip -d /tmp/
    sudo /tmp/aws/install
    rm -rf /tmp/aws /tmp/awscliv2.zip
fi
aws --version

# ── 2. Apache ─────────────────────────────────────────────────────────────────
echo ">>> Instalando Apache..."
sudo dnf install -y httpd
sudo systemctl enable httpd
sudo systemctl start httpd

# ── 3. Git ────────────────────────────────────────────────────────────────────
echo ">>> Instalando Git..."
sudo dnf install -y git
git --version

# ── 4. CloudWatch Agent ───────────────────────────────────────────────────────
echo ">>> Instalando CloudWatch Agent..."
sudo dnf install -y amazon-cloudwatch-agent
sudo mkdir -p /opt/aws/amazon-cloudwatch-agent/etc

sudo tee /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json > /dev/null << 'CWCONFIG'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "metrics": {
    "namespace": "CustomMetrics/EC2",
    "metrics_collected": {
      "mem": {
        "measurement": ["mem_used_percent", "mem_used", "mem_available", "mem_total"],
        "metrics_collection_interval": 60
      },
      "swap": {
        "measurement": ["swap_used_percent"],
        "metrics_collection_interval": 60
      }
    },
    "append_dimensions": {
      "InstanceId": "${aws:InstanceId}",
      "AutoScalingGroupName": "${aws:AutoScalingGroupName}"
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/httpd/access_log",
            "log_group_name": "/app/httpd/access",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/httpd/error_log",
            "log_group_name": "/app/httpd/error",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/user-data.log",
            "log_group_name": "/app/user-data",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
CWCONFIG

sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
    -s

sudo systemctl enable amazon-cloudwatch-agent

# ── 5. Script de métricas de memoria ─────────────────────────────────────────
echo ">>> Configurando métricas de memoria..."
sudo tee /usr/local/bin/push-memory-metrics.sh > /dev/null << 'MEMSCRIPT'
#!/bin/bash
INSTANCE_ID=$(curl -sf http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -sf http://169.254.169.254/latest/meta-data/placement/region)
ASG_NAME=$(aws autoscaling describe-auto-scaling-instances \
    --instance-ids "$INSTANCE_ID" \
    --query "AutoScalingInstances[0].AutoScalingGroupName" \
    --output text 2>/dev/null || echo "standalone")

MEM_TOTAL=$(awk '/MemTotal/  {print $2}' /proc/meminfo)
MEM_AVAIL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
MEM_USED=$((MEM_TOTAL - MEM_AVAIL))
MEM_PCT=$(awk "BEGIN {printf \"%.2f\", ($MEM_USED/$MEM_TOTAL)*100}")

aws cloudwatch put-metric-data \
    --region "$REGION" \
    --namespace "CustomMetrics/EC2" \
    --metric-data \
        MetricName=MemoryUtilization,Value="$MEM_PCT",Unit=Percent,\
Dimensions=[{Name=InstanceId,Value="$INSTANCE_ID"},{Name=AutoScalingGroupName,Value="$ASG_NAME"}]
MEMSCRIPT

sudo chmod +x /usr/local/bin/push-memory-metrics.sh
echo "* * * * * root /usr/local/bin/push-memory-metrics.sh >> /var/log/memory-metrics.log 2>&1" \
    | sudo tee /etc/cron.d/memory-metrics

# ── 6. SSM Agent ──────────────────────────────────────────────────────────────
echo ">>> Configurando SSM Agent..."
sudo dnf install -y amazon-ssm-agent
sudo systemctl enable amazon-ssm-agent
sudo systemctl start amazon-ssm-agent
sudo systemctl status amazon-ssm-agent --no-pager

# ── Limpieza ──────────────────────────────────────────────────────────────────
echo ">>> Limpiando para snapshot..."
sudo dnf clean all
sudo rm -rf /var/cache/dnf
sudo rm -f /etc/ssh/ssh_host_*
sudo rm -f /root/.ssh/authorized_keys
sudo rm -f /home/ec2-user/.ssh/authorized_keys
sudo truncate -s 0 /var/log/cloud-init*.log
sudo truncate -s 0 /var/log/messages

echo "=== DONE: $(date) ==="
