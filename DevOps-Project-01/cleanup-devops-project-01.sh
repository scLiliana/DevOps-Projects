#!/bin/bash
# =============================================================================
# cleanup-devops-project-01.sh
# Elimina TODOS los recursos de AWS creados en DevOps-Project-01
# en el orden correcto (respetando dependencias entre recursos)
#
# USO:
#   chmod +x cleanup-devops-project-01.sh
#   ./cleanup-devops-project-01.sh
#
# REQUISITOS:
#   - AWS CLI configurado (aws configure)
#   - Permisos suficientes en la cuenta AWS
# =============================================================================

set -e  # Detener si hay error crítico

# ─── COLORES PARA OUTPUT ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Sin color

log()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()     { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()   { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()  { echo -e "${RED}[ERROR]${NC} $1"; }
header() { echo -e "\n${YELLOW}══════════════════════════════════════${NC}"; echo -e "${YELLOW} $1${NC}"; echo -e "${YELLOW}══════════════════════════════════════${NC}"; }

# ─── CONFIGURACIÓN — EDITA ESTOS VALORES ─────────────────────────────────────
REGION="us-east-1"

# Si los tienes, pégalos aquí. Si los dejas vacíos, el script los buscará automáticamente.
VPC_NAME="PrimaryVPC"
S3_BUCKET_NAME=""           # Ej: "mi-bucket-logs-tomcat"
RDS_IDENTIFIER="prod-mysql"
DB_SUBNET_GROUP="mydbsubnetgroup"
ASG_TOMCAT="tomcat-asg"
ASG_NGINX="nginx-asg"
LC_TOMCAT="TomcatLC"        # ya no se usa — se eliminan Launch Templates
LC_NGINX="NginxLC"          # ya no se usa — se eliminan Launch Templates
LT_TOMCAT="TomcatLT"
LT_NGINX="NginxLT"
NLB_PUBLIC="public-nlb"
NLB_PRIVATE="private-nlb"
TG_TOMCAT="tomcat-tg"
TG_NGINX="nginx-tg"
IAM_ROLE="EC2AppRole"
IAM_PROFILE="EC2AppProfile"
IAM_POLICY_NAME="AppS3Policy"
BASTION_NAME="BastionHost"

# ─── CONFIRMACIÓN ─────────────────────────────────────────────────────────────
echo ""
echo -e "${RED}╔══════════════════════════════════════════════╗${NC}"
echo -e "${RED}║   ⚠️  ADVERTENCIA: ELIMINACIÓN DE RECURSOS   ║${NC}"
echo -e "${RED}║   Esta acción es IRREVERSIBLE                ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "Se eliminarán los siguientes recursos en la región: $REGION"
echo "  - Auto Scaling Groups (nginx-asg, tomcat-asg)"
echo "  - Launch Configurations"
echo "  - Network Load Balancers (público y privado)"
echo "  - Target Groups"
echo "  - EC2 Instances (Bastion + Maven)"
echo "  - RDS Instance ($RDS_IDENTIFIER)"
echo "  - NAT Gateways + Elastic IPs"
echo "  - Internet Gateway"
echo "  - Subnets, Route Tables, Security Groups"
echo "  - VPC ($VPC_NAME)"
echo "  - IAM Role + Instance Profile + Policy"
echo "  - S3 Bucket (si se especificó)"
echo ""
read -p "¿Estás seguro? Escribe 'ELIMINAR' para continuar: " CONFIRM

if [ "$CONFIRM" != "ELIMINAR" ]; then
    echo "Operación cancelada."
    exit 0
fi

# ─── OBTENER VPC ID ───────────────────────────────────────────────────────────
header "0. Obteniendo IDs base"

VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=$VPC_NAME" \
    --query "Vpcs[0].VpcId" \
    --output text \
    --region $REGION 2>/dev/null || echo "")

if [ "$VPC_ID" == "None" ] || [ -z "$VPC_ID" ]; then
    warn "No se encontró la VPC con nombre '$VPC_NAME'. Algunos pasos pueden fallar."
else
    log "VPC encontrada: $VPC_ID"
fi

# ─── 1. AUTO SCALING GROUPS ───────────────────────────────────────────────────
header "1. Eliminando Auto Scaling Groups"

for ASG in $ASG_NGINX $ASG_TOMCAT; do
    EXISTS=$(aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names $ASG \
        --query "AutoScalingGroups[0].AutoScalingGroupName" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$EXISTS" != "None" ] && [ -n "$EXISTS" ]; then
        log "Eliminando ASG: $ASG"
        aws autoscaling update-auto-scaling-group \
            --auto-scaling-group-name $ASG \
            --min-size 0 --max-size 0 --desired-capacity 0 \
            --region $REGION
        sleep 15  # esperar que las instancias se terminen
        aws autoscaling delete-auto-scaling-group \
            --auto-scaling-group-name $ASG \
            --force-delete \
            --region $REGION
        ok "ASG $ASG eliminado"
    else
        warn "ASG $ASG no encontrado, omitiendo"
    fi
done

# ─── 2. LAUNCH TEMPLATES ──────────────────────────────────────────────────────
header "2. Eliminando Launch Templates"

for LT in $LT_NGINX $LT_TOMCAT; do
    EXISTS=$(aws ec2 describe-launch-templates \
        --launch-template-names $LT \
        --query "LaunchTemplates[0].LaunchTemplateName" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$EXISTS" != "None" ] && [ -n "$EXISTS" ]; then
        aws ec2 delete-launch-template \
            --launch-template-name $LT \
            --region $REGION
        ok "Launch Template $LT eliminado"
    else
        warn "Launch Template $LT no encontrado, omitiendo"
    fi
done

# También eliminar Launch Configurations si existieran (cuentas antiguas)
for LC in $LC_NGINX $LC_TOMCAT; do
    EXISTS=$(aws autoscaling describe-launch-configurations \
        --launch-configuration-names $LC \
        --query "LaunchConfigurations[0].LaunchConfigurationName" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$EXISTS" != "None" ] && [ -n "$EXISTS" ]; then
        aws autoscaling delete-launch-configuration \
            --launch-configuration-name $LC \
            --region $REGION
        ok "Launch Configuration $LC eliminada"
    else
        warn "LC $LC no encontrada, omitiendo"
    fi
done

# ─── 3. LOAD BALANCERS ────────────────────────────────────────────────────────
header "3. Eliminando Load Balancers"

for NLB in $NLB_PUBLIC $NLB_PRIVATE; do
    NLB_ARN=$(aws elbv2 describe-load-balancers \
        --names $NLB \
        --query "LoadBalancers[0].LoadBalancerArn" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$NLB_ARN" != "None" ] && [ -n "$NLB_ARN" ]; then
        log "Eliminando listeners del NLB: $NLB"
        LISTENERS=$(aws elbv2 describe-listeners \
            --load-balancer-arn $NLB_ARN \
            --query "Listeners[*].ListenerArn" \
            --output text --region $REGION 2>/dev/null || echo "")

        for LISTENER in $LISTENERS; do
            aws elbv2 delete-listener --listener-arn $LISTENER --region $REGION
        done

        log "Eliminando NLB: $NLB"
        aws elbv2 delete-load-balancer \
            --load-balancer-arn $NLB_ARN \
            --region $REGION
        ok "NLB $NLB eliminado"
    else
        warn "NLB $NLB no encontrado, omitiendo"
    fi
done

log "Esperando 30s para que los NLBs terminen de eliminarse..."
sleep 30

# ─── 4. TARGET GROUPS ─────────────────────────────────────────────────────────
header "4. Eliminando Target Groups"

for TG in $TG_TOMCAT $TG_NGINX; do
    TG_ARN=$(aws elbv2 describe-target-groups \
        --names $TG \
        --query "TargetGroups[0].TargetGroupArn" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$TG_ARN" != "None" ] && [ -n "$TG_ARN" ]; then
        aws elbv2 delete-target-group \
            --target-group-arn $TG_ARN \
            --region $REGION
        ok "Target Group $TG eliminado"
    else
        warn "Target Group $TG no encontrado, omitiendo"
    fi
done

# ─── 5. INSTANCIAS EC2 ────────────────────────────────────────────────────────
header "5. Terminando instancias EC2"

for NAME in $BASTION_NAME "MavenBuildServer"; do
    INSTANCE_IDS=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=running,stopped" \
        --query "Reservations[*].Instances[*].InstanceId" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ -n "$INSTANCE_IDS" ]; then
        log "Terminando instancia(s): $NAME ($INSTANCE_IDS)"
        aws ec2 terminate-instances \
            --instance-ids $INSTANCE_IDS \
            --region $REGION
        ok "Instancia(s) $NAME en proceso de terminación"
    else
        warn "Instancia $NAME no encontrada, omitiendo"
    fi
done

log "Esperando 30s para que las instancias terminen..."
sleep 30

# ─── 6. RDS ───────────────────────────────────────────────────────────────────
header "6. Eliminando RDS"

RDS_STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier $RDS_IDENTIFIER \
    --query "DBInstances[0].DBInstanceStatus" \
    --output text --region $REGION 2>/dev/null || echo "not-found")

if [ "$RDS_STATUS" != "not-found" ] && [ "$RDS_STATUS" != "None" ]; then
    log "Eliminando RDS: $RDS_IDENTIFIER (puede tardar 5-10 min)"
    aws rds delete-db-instance \
        --db-instance-identifier $RDS_IDENTIFIER \
        --skip-final-snapshot \
        --delete-automated-backups \
        --region $REGION
    
    log "Esperando que RDS se elimine completamente..."
    aws rds wait db-instance-deleted \
        --db-instance-identifier $RDS_IDENTIFIER \
        --region $REGION
    ok "RDS $RDS_IDENTIFIER eliminado"
else
    warn "RDS $RDS_IDENTIFIER no encontrado, omitiendo"
fi

# Eliminar DB Subnet Group
SUBNET_GROUP_EXISTS=$(aws rds describe-db-subnet-groups \
    --db-subnet-group-name $DB_SUBNET_GROUP \
    --query "DBSubnetGroups[0].DBSubnetGroupName" \
    --output text --region $REGION 2>/dev/null || echo "")

if [ -n "$SUBNET_GROUP_EXISTS" ] && [ "$SUBNET_GROUP_EXISTS" != "None" ]; then
    aws rds delete-db-subnet-group \
        --db-subnet-group-name $DB_SUBNET_GROUP \
        --region $REGION
    ok "DB Subnet Group $DB_SUBNET_GROUP eliminado"
fi

# ─── 7. NAT GATEWAYS ──────────────────────────────────────────────────────────
header "7. Eliminando NAT Gateways"

NAT_IDS=$(aws ec2 describe-nat-gateways \
    --filter "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available,pending" \
    --query "NatGateways[*].NatGatewayId" \
    --output text --region $REGION 2>/dev/null || echo "")

for NAT_ID in $NAT_IDS; do
    log "Eliminando NAT Gateway: $NAT_ID"
    aws ec2 delete-nat-gateway \
        --nat-gateway-id $NAT_ID \
        --region $REGION
    ok "NAT Gateway $NAT_ID en proceso de eliminación"
done

if [ -n "$NAT_IDS" ]; then
    log "Esperando a que los NAT Gateways queden en estado 'deleted' (~90s)..."
    sleep 30
    # Esperar activamente hasta que todos estén deleted
    for NAT_ID in $NAT_IDS; do
        for i in {1..10}; do
            STATE=$(aws ec2 describe-nat-gateways \
                --nat-gateway-ids $NAT_ID \
                --query "NatGateways[0].State" \
                --output text --region $REGION 2>/dev/null || echo "deleted")
            if [ "$STATE" == "deleted" ]; then
                ok "NAT Gateway $NAT_ID eliminado"
                break
            fi
            log "NAT $NAT_ID estado: $STATE — esperando 15s más..."
            sleep 15
        done
    done
fi

# ─── 8. ELASTIC IPs ───────────────────────────────────────────────────────────
header "8. Liberando Elastic IPs"

# Primero desasociar las que estén asociadas a instancias o NAT Gateways
ASSOC_IDS=$(aws ec2 describe-addresses \
    --filters "Name=domain,Values=vpc" \
    --query "Addresses[?AssociationId!=null].AssociationId" \
    --output text --region $REGION 2>/dev/null || echo "")

for ASSOC_ID in $ASSOC_IDS; do
    log "Desasociando Elastic IP: $ASSOC_ID"
    aws ec2 disassociate-address \
        --association-id $ASSOC_ID \
        --region $REGION 2>/dev/null && ok "EIP desasociada" || \
        warn "No se pudo desasociar $ASSOC_ID"
done

# Ahora liberar todas las EIPs
EIP_ALLOC_IDS=$(aws ec2 describe-addresses \
    --filters "Name=domain,Values=vpc" \
    --query "Addresses[*].AllocationId" \
    --output text --region $REGION 2>/dev/null || echo "")

for EIP_ID in $EIP_ALLOC_IDS; do
    log "Liberando Elastic IP: $EIP_ID"
    aws ec2 release-address \
        --allocation-id $EIP_ID \
        --region $REGION 2>/dev/null && ok "Elastic IP $EIP_ID liberada" || \
        warn "No se pudo liberar $EIP_ID — puede estar aún asociada a un NAT Gateway en eliminación"
done

# ─── 9. INTERNET GATEWAY ──────────────────────────────────────────────────────
header "9. Desconectando y eliminando Internet Gateway"

IGW_ID=$(aws ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --query "InternetGateways[0].InternetGatewayId" \
    --output text --region $REGION 2>/dev/null || echo "")

if [ "$IGW_ID" != "None" ] && [ -n "$IGW_ID" ]; then
    aws ec2 detach-internet-gateway \
        --internet-gateway-id $IGW_ID \
        --vpc-id $VPC_ID \
        --region $REGION
    aws ec2 delete-internet-gateway \
        --internet-gateway-id $IGW_ID \
        --region $REGION
    ok "Internet Gateway $IGW_ID eliminado"
else
    warn "Internet Gateway no encontrado, omitiendo"
fi

# ─── 10. TRANSIT GATEWAY ATTACHMENTS ─────────────────────────────────────────
header "10. Eliminando Transit Gateway Attachments"

TGW_ATTACH_IDS=$(aws ec2 describe-transit-gateway-vpc-attachments \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available,pending,modifying" \
    --query "TransitGatewayVpcAttachments[*].TransitGatewayAttachmentId" \
    --output text --region $REGION 2>/dev/null || echo "")

for ATTACH_ID in $TGW_ATTACH_IDS; do
    log "Eliminando TGW Attachment: $ATTACH_ID"
    aws ec2 delete-transit-gateway-vpc-attachment \
        --transit-gateway-attachment-id $ATTACH_ID \
        --region $REGION
    ok "TGW Attachment $ATTACH_ID en proceso de eliminación"
done

if [ -n "$TGW_ATTACH_IDS" ]; then
    log "Esperando 60s para que los TGW Attachments se eliminen..."
    sleep 60
fi

# ─── 11. SUBNETS ──────────────────────────────────────────────────────────────
header "11. Eliminando Subnets"

SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" \
    --output text --region $REGION 2>/dev/null || echo "")

for SUBNET_ID in $SUBNET_IDS; do
    # Verificar si hay ENIs activos en la subnet antes de intentar eliminarla
    ENI_COUNT=$(aws ec2 describe-network-interfaces \
        --filters "Name=subnet-id,Values=$SUBNET_ID" \
        --query "length(NetworkInterfaces)" \
        --output text --region $REGION 2>/dev/null || echo "0")

    if [ "$ENI_COUNT" != "0" ] && [ -n "$ENI_COUNT" ]; then
        warn "Subnet $SUBNET_ID tiene $ENI_COUNT ENI(s) activos — esperando 30s..."
        sleep 30
    fi

    log "Eliminando subnet: $SUBNET_ID"
    aws ec2 delete-subnet \
        --subnet-id $SUBNET_ID \
        --region $REGION 2>/dev/null && ok "Subnet $SUBNET_ID eliminada" || \
        warn "Subnet $SUBNET_ID no se pudo eliminar — puede tener dependencias activas"
done

# ─── 12. ROUTE TABLES ─────────────────────────────────────────────────────────
header "12. Eliminando Route Tables"

RT_IDS=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "RouteTables[?Associations[0].Main!=\`true\`].RouteTableId" \
    --output text --region $REGION 2>/dev/null || echo "")

for RT_ID in $RT_IDS; do
    log "Eliminando Route Table: $RT_ID"
    aws ec2 delete-route-table \
        --route-table-id $RT_ID \
        --region $REGION
    ok "Route Table $RT_ID eliminada"
done

# ─── 13. SECURITY GROUPS ──────────────────────────────────────────────────────
header "13. Eliminando Security Groups"

SG_IDS=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[?GroupName!='default'].GroupId" \
    --output text --region $REGION 2>/dev/null || echo "")

for SG_ID in $SG_IDS; do
    log "Eliminando Security Group: $SG_ID"
    aws ec2 delete-security-group \
        --group-id $SG_ID \
        --region $REGION 2>/dev/null && ok "SG $SG_ID eliminado" || \
        warn "SG $SG_ID no se pudo eliminar (puede tener dependencias aún activas)"
done

# ─── 14. VPC ──────────────────────────────────────────────────────────────────
header "14. Eliminando VPC"

if [ "$VPC_ID" != "None" ] && [ -n "$VPC_ID" ]; then
    # Verificar si quedan IGWs adjuntos (pueden haber reaparecido)
    IGW_ID=$(aws ec2 describe-internet-gateways \
        --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
        --query "InternetGateways[0].InternetGatewayId" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$IGW_ID" != "None" ] && [ -n "$IGW_ID" ]; then
        log "IGW encontrado aún adjunto: $IGW_ID — desconectando..."
        aws ec2 detach-internet-gateway \
            --internet-gateway-id $IGW_ID \
            --vpc-id $VPC_ID --region $REGION 2>/dev/null
        aws ec2 delete-internet-gateway \
            --internet-gateway-id $IGW_ID \
            --region $REGION 2>/dev/null
        ok "IGW $IGW_ID eliminado"
    fi

    # Verificar si quedan SGs (aparte del default)
    REMAINING_SGS=$(aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[?GroupName!='default'].GroupId" \
        --output text --region $REGION 2>/dev/null || echo "")

    for SG_ID in $REMAINING_SGS; do
        log "Eliminando SG remanente: $SG_ID"
        aws ec2 delete-security-group \
            --group-id $SG_ID --region $REGION 2>/dev/null
    done

    # Intentar eliminar la VPC
    aws ec2 delete-vpc \
        --vpc-id $VPC_ID \
        --region $REGION && ok "VPC $VPC_ID eliminada" || {
        error "No se pudo eliminar la VPC — verificar dependencias restantes:"
        aws ec2 describe-network-interfaces \
            --filters "Name=vpc-id,Values=$VPC_ID" \
            --query "NetworkInterfaces[*].[NetworkInterfaceId,Status,Description]" \
            --output table --region $REGION 2>/dev/null
    }
else
    warn "VPC no encontrada, omitiendo"
fi

# ─── 15. IAM ──────────────────────────────────────────────────────────────────
header "15. Eliminando IAM Role, Instance Profile y Policy"

# Remover rol del instance profile
aws iam remove-role-from-instance-profile \
    --instance-profile-name $IAM_PROFILE \
    --role-name $IAM_ROLE 2>/dev/null && log "Rol removido del Instance Profile" || \
    warn "No se pudo remover el rol del Instance Profile (puede no existir)"

# Eliminar instance profile
aws iam delete-instance-profile \
    --instance-profile-name $IAM_PROFILE 2>/dev/null && ok "Instance Profile eliminado" || \
    warn "Instance Profile no encontrado"

# Desadjuntar políticas del rol
POLICY_ARNS=$(aws iam list-attached-role-policies \
    --role-name $IAM_ROLE \
    --query "AttachedPolicies[*].PolicyArn" \
    --output text 2>/dev/null || echo "")

for POLICY_ARN in $POLICY_ARNS; do
    log "Desadjuntando política: $POLICY_ARN"
    aws iam detach-role-policy \
        --role-name $IAM_ROLE \
        --policy-arn $POLICY_ARN 2>/dev/null
done

# Eliminar el rol
aws iam delete-role \
    --role-name $IAM_ROLE 2>/dev/null && ok "IAM Role $IAM_ROLE eliminado" || \
    warn "IAM Role no encontrado"

# Eliminar la política personalizada
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
CUSTOM_POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${IAM_POLICY_NAME}"

aws iam delete-policy \
    --policy-arn $CUSTOM_POLICY_ARN 2>/dev/null && ok "Policy $IAM_POLICY_NAME eliminada" || \
    warn "Policy no encontrada"

# ─── 16. S3 ───────────────────────────────────────────────────────────────────
header "16. Eliminando S3 Bucket"

if [ -n "$S3_BUCKET_NAME" ]; then
    # Verificar que el bucket existe
    BUCKET_EXISTS=$(aws s3api head-bucket \
        --bucket $S3_BUCKET_NAME \
        --region $REGION 2>/dev/null && echo "yes" || echo "no")

    if [ "$BUCKET_EXISTS" == "yes" ]; then
        log "Vaciando bucket: $S3_BUCKET_NAME"

        # Paso 1 — Eliminar todos los objetos normales
        log "Eliminando objetos..."
        aws s3 rm s3://$S3_BUCKET_NAME \
            --recursive \
            --region $REGION 2>/dev/null
        ok "Objetos eliminados"

        # Paso 2 — Eliminar versiones antiguas (si el bucket tiene versionado habilitado)
        log "Eliminando versiones de objetos..."
        VERSIONS=$(aws s3api list-object-versions \
            --bucket $S3_BUCKET_NAME \
            --query "Versions[*].{Key:Key,VersionId:VersionId}" \
            --output json --region $REGION 2>/dev/null || echo "[]")

        if [ "$VERSIONS" != "[]" ] && [ -n "$VERSIONS" ]; then
            echo "$VERSIONS" | python3 -c "
import sys, json, subprocess
versions = json.load(sys.stdin)
for v in versions:
    cmd = ['aws', 's3api', 'delete-object',
           '--bucket', '$S3_BUCKET_NAME',
           '--key', v['Key'],
           '--version-id', v['VersionId'],
           '--region', '$REGION']
    subprocess.run(cmd, capture_output=True)
    print(f'  Versión eliminada: {v[\"Key\"]} ({v[\"VersionId\"]})')
" 2>/dev/null
            ok "Versiones eliminadas"
        fi

        # Paso 3 — Eliminar delete markers
        log "Eliminando delete markers..."
        MARKERS=$(aws s3api list-object-versions \
            --bucket $S3_BUCKET_NAME \
            --query "DeleteMarkers[*].{Key:Key,VersionId:VersionId}" \
            --output json --region $REGION 2>/dev/null || echo "[]")

        if [ "$MARKERS" != "[]" ] && [ -n "$MARKERS" ]; then
            echo "$MARKERS" | python3 -c "
import sys, json, subprocess
markers = json.load(sys.stdin)
for m in markers:
    cmd = ['aws', 's3api', 'delete-object',
           '--bucket', '$S3_BUCKET_NAME',
           '--key', m['Key'],
           '--version-id', m['VersionId'],
           '--region', '$REGION']
    subprocess.run(cmd, capture_output=True)
    print(f'  Delete marker eliminado: {m[\"Key\"]}')
" 2>/dev/null
            ok "Delete markers eliminados"
        fi

        # Paso 4 — Eliminar el bucket ya vacío
        log "Eliminando bucket: $S3_BUCKET_NAME"
        aws s3api delete-bucket \
            --bucket $S3_BUCKET_NAME \
            --region $REGION && ok "S3 Bucket $S3_BUCKET_NAME eliminado" || \
            warn "No se pudo eliminar el bucket — puede quedar contenido con versionado"
    else
        warn "S3 Bucket $S3_BUCKET_NAME no encontrado, omitiendo"
    fi
else
    # Si no se especificó nombre, intentar encontrarlo automáticamente
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    AUTO_BUCKET="devops-project-01-logs-${ACCOUNT_ID}"
    log "S3_BUCKET_NAME no especificado — buscando bucket automático: $AUTO_BUCKET"

    BUCKET_EXISTS=$(aws s3api head-bucket \
        --bucket $AUTO_BUCKET \
        --region $REGION 2>/dev/null && echo "yes" || echo "no")

    if [ "$BUCKET_EXISTS" == "yes" ]; then
        S3_BUCKET_NAME=$AUTO_BUCKET
        log "Bucket encontrado: $S3_BUCKET_NAME — vaciando..."
        aws s3 rm s3://$S3_BUCKET_NAME --recursive --region $REGION 2>/dev/null
        aws s3api delete-bucket \
            --bucket $S3_BUCKET_NAME \
            --region $REGION && ok "S3 Bucket $S3_BUCKET_NAME eliminado" || \
            warn "No se pudo eliminar el bucket"
    else
        warn "No se encontró ningún bucket de este proyecto, omitiendo"
    fi
fi

# ─── 17. TRANSIT GATEWAY ──────────────────────────────────────────────────────
header "17. Eliminando Transit Gateway"

TGW_IDS=$(aws ec2 describe-transit-gateways \
    --filters "Name=state,Values=available" \
    --query "TransitGateways[*].TransitGatewayId" \
    --output text --region $REGION 2>/dev/null || echo "")

for TGW_ID in $TGW_IDS; do
    log "Eliminando Transit Gateway: $TGW_ID"
    aws ec2 delete-transit-gateway \
        --transit-gateway-id $TGW_ID \
        --region $REGION 2>/dev/null && ok "Transit Gateway $TGW_ID eliminado" || \
        warn "No se pudo eliminar $TGW_ID — puede tener attachments activos aún"
done

if [ -z "$TGW_IDS" ]; then
    warn "No se encontraron Transit Gateways, omitiendo"
fi

# ─── 18. AMIs Y SNAPSHOTS ─────────────────────────────────────────────────────
header "18. Eliminando AMIs y Snapshots"

AMI_NAMES=("GlobalAMI-Base" "NginxGoldenAMI" "TomcatGoldenAMI" "MavenGoldenAMI")

for AMI_NAME in "${AMI_NAMES[@]}"; do
    AMI_ID=$(aws ec2 describe-images \
        --owners self \
        --filters "Name=name,Values=$AMI_NAME" \
        --query "Images[0].ImageId" \
        --output text --region $REGION 2>/dev/null || echo "")

    if [ "$AMI_ID" != "None" ] && [ -n "$AMI_ID" ]; then
        # Obtener snapshots asociados antes de desregistrar
        SNAPSHOT_IDS=$(aws ec2 describe-images \
            --image-ids $AMI_ID \
            --query "Images[0].BlockDeviceMappings[*].Ebs.SnapshotId" \
            --output text --region $REGION 2>/dev/null || echo "")

        log "Desregistrando AMI: $AMI_NAME ($AMI_ID)"
        aws ec2 deregister-image \
            --image-id $AMI_ID \
            --region $REGION
        ok "AMI $AMI_NAME desregistrada"

        # Eliminar snapshots asociados
        for SNAP_ID in $SNAPSHOT_IDS; do
            if [ "$SNAP_ID" != "None" ] && [ -n "$SNAP_ID" ]; then
                log "Eliminando snapshot: $SNAP_ID"
                aws ec2 delete-snapshot \
                    --snapshot-id $SNAP_ID \
                    --region $REGION 2>/dev/null && ok "Snapshot $SNAP_ID eliminado" || \
                    warn "No se pudo eliminar snapshot $SNAP_ID"
            fi
        done
    else
        warn "AMI '$AMI_NAME' no encontrada, omitiendo"
    fi
done

# ─── RESUMEN ──────────────────────────────────────────────────────────────────
header "✅ Limpieza completada"

echo ""
echo "Recursos procesados en orden:"
echo "  ✓  1. Auto Scaling Groups (tomcat-asg, nginx-asg)"
echo "  ✓  2. Launch Templates (TomcatLT, NginxLT)"
echo "  ✓  3. Load Balancers (public-nlb, private-nlb)"
echo "  ✓  4. Target Groups (tomcat-tg, nginx-tg)"
echo "  ✓  5. Instancias EC2 (Bastion, Maven)"
echo "  ✓  6. RDS y DB Subnet Group"
echo "  ✓  7. NAT Gateways (espera activa hasta estado deleted)"
echo "  ✓  8. Elastic IPs (desasociar + liberar)"
echo "  ✓  9. Internet Gateway"
echo "  ✓ 10. Transit Gateway Attachments"
echo "  ✓ 11. Subnets"
echo "  ✓ 12. Route Tables"
echo "  ✓ 13. Security Groups"
echo "  ✓ 14. VPC"
echo "  ✓ 15. IAM Role, Instance Profile y Policy"
echo "  ✓ 16. S3 Bucket"
echo "  ✓ 17. Transit Gateway"
echo "  ✓ 18. AMIs y Snapshots"
echo ""
echo -e "${YELLOW}Verifica en la consola AWS que no queden recursos activos:${NC}"
echo "  → https://us-east-1.console.aws.amazon.com/ec2/home"
echo "  → https://console.aws.amazon.com/vpc/home"
echo "  → https://console.aws.amazon.com/rds/home"
echo "  → https://console.aws.amazon.com/billing/home (para evitar cargos)"
echo ""
echo -e "${YELLOW}Recursos que debes verificar manualmente:${NC}"
echo "  → EC2 → AMIs → Filtrar por 'owner: me' para confirmar que no quedan AMIs"
echo "  → EC2 → Snapshots → Filtrar por 'owner: me' para confirmar que no quedan snapshots"
echo "  → VPC → Transit Gateways → Verificar si quedan TGWs de este proyecto"
echo "  → Key Pairs → 'DevOpsKeyPair' (eliminar si ya no la necesitas)"
echo ""