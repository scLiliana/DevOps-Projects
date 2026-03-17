[[1.DevOps-Proyect-01]][[Infra DevOps]][[AWS]]
### Permitir SSH desde tu IP al SG default

**Pre-requisito:** ```$DEFAULT_SG ```

```bash

aws ec2 authorize-security-group-ingress \
    --group-id $DEFAULT_SG \
    --protocol tcp \
    --port 22 \
    --cidr $(curl -s https://checkip.amazonaws.com)/32 \
    --region us-east-1

```
