[[1.DevOps-Proyect-01]][[Infra DevOps]][[AWS]]
## Para guardar los IDs directamente en variables:

### ID instancia
```bash
# Guardar ID de instancia por nombre

INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=MavenGoldenAMI-Instance" \
              "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region $REGION)
    
echo "INSTANCE_ID: $INSTANCE_ID"
```

### ID AMI
```bash 
# Guardar ID de AMI por nombre

AMI_ID=$(aws ec2 describe-images \
    --owners self \
    --filters "Name=name,Values=TomcatGoldenAMI" \
    --query "Images[0].ImageId" \
    --output text --region $REGION)
    
echo "AMI_ID: $AMI_ID"
```

Solo cambia el `Values=` con el nombre exacto que le pusiste a tu instancia o AMI.

## Para consultar una tabla con todos los IDs:

### Instancias
```bash

echo "==============================="
echo "INSTANCIAS EC2 ACTIVAS"
echo "==============================="
aws ec2 describe-instances \
    --filters "Name=instance-state-name,Values=running,stopped" \
    --query "Reservations[].Instances[].[InstanceId, PublicIpAddress, Tags[?Key=='Name'].Value|[0], State.Name]" \
    --output table \
    --region us-east-1
```
### AMIs
```bash
echo "==============================="
echo "AMIs PROPIAS CREADAS POR TI"
echo "==============================="
aws ec2 describe-images \
    --owners self \
    --query "Images[].[ImageId, Name, CreationDate, State]" \
    --output table \
    --region us-east-1

```