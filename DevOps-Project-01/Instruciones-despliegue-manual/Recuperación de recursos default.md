[[1.DevOps-Proyect-01]][[Infra DevOps]][[AWS]]
### Antes de empezar — Obtener recursos de la Default VPC

Las instancias de este paso son **temporales**. Se usan para instalar software, crear la AMI y luego se terminan. Por eso usamos la Default VPC que ya existe en toda cuenta AWS, sin necesidad de crear nada de red todavía.
## ID de la Default VPC

```bash
# Guarda el ID de la VPC en la variable DEFAULT_VPC

DEFAULT_VPC=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text \
    --region us-east-1)
    
echo "Default VPC: $DEFAULT_VPC"

```

## ID de la Default Subnet

**Pre-requisito:** ```$DEFAULT_VPC ```

```bash
# Guarda el ID de la Subnet en la variable DEFAULT_SUBNET

DEFAULT_SUBNET=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
    --query "Subnets[0].SubnetId" \
    --output text \
    --region us-east-1)
    
echo "Subnet: $DEFAULT_SUBNET"

```

## ID del Security Group Default

**Pre-requisito:** ```$DEFAULT_VPC ```

```bash

# Guarda el ID de la Security Group en la variable DEFAULT_SG

DEFAULT_SG=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
              "Name=group-name,Values=default" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region us-east-1)
    
echo "Security Group: $DEFAULT_SG"

```

