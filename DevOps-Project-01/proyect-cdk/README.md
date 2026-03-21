# DevOps Project-01 — CDK Python

Infraestructura como código para desplegar la arquitectura 3-tier en AWS usando EC2 Image Builder para crear las Golden AMIs automáticamente.

## Arquitectura

```
Internet
   │
   ▼
Public NLB  (Subnet pública)
   │
   ▼
Nginx ASG   (Subnet privada AZ-1a / AZ-1b)   ← FrontendSG
   │  proxy_pass →
   ▼
Private NLB (Subnet privada)
   │
   ▼
Tomcat ASG  (Subnet privada AZ-1a / AZ-1b)   ← BackendSG
   │
   ▼
MySQL RDS Multi-AZ (Subnet aislada)           ← DatabaseSG
```

---

## Stacks (7 en total)

| # | Stack | Recursos |
|---|---|---|
| 0 | `ImageBuilderStack` | EC2 Image Builder Pipelines → Golden AMIs |
| 1 | `NetworkingStack` | VPC, Subnets, IGW, NAT Gateways, Route Tables |
| 2 | `SecurityStack` | Security Groups (Bastion/Frontend/Backend/Database), IAM Role |
| 3 | `StorageStack` | S3 Bucket (logs), SNS Topic, CloudWatch Alarms |
| 4 | `DatabaseStack` | RDS MySQL 8.0 Multi-AZ, DB Subnet Group, Parameter Group |
| 5 | `BackendStack` | Launch Template Tomcat, ASG, Target Group, NLB interno |
| 6 | `FrontendStack` | Launch Template Nginx, ASG, Target Group, NLB público |

---

## Pre-requisitos

```bash
# 1. Node.js 18+ y CDK CLI
node --version          # debe ser >= 18
npm install -g aws-cdk
cdk --version           # debe ser >= 2.100.0

# 2. Python 3.8+
python3 --version

# 3. AWS CLI configurado
aws configure
aws sts get-caller-identity   # verificar credenciales

# 4. Entorno virtual y dependencias
python3 -m venv .venv
source .venv/bin/activate     # Linux/Mac
# .venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 5. Bootstrap CDK en tu cuenta (solo la primera vez)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cdk bootstrap aws://$ACCOUNT_ID/us-east-1

# 6. Listar stacks para verificar que todo está bien
cdk list
```

Debe mostrar los  stacks:
```
NetworkingStack
SecurityStack
StorageStack
DatabaseStack
TargetGroupsStack
NlbStack
LaunchTemplateStack
ASGStack
```

---

## Configuración — editar app.py antes de desplegar

Abre `app.py` y completa el bloque `config` con tus valores reales:

```python
config = {
    # Tu IP pública — obtenerla con: curl https://checkip.amazonaws.com
    "your_ip":      "X.X.X.X/32",

    # Email para recibir alertas de CloudWatch
    "alert_email":  "tu@email.com",

    # Contraseña del usuario admin de RDS (mín 8 chars, mayúscula, número)
    "db_password":  "TuPasswordSegura123!",

    # IDs de las Golden AMIs — se obtienen después de ejecutar los pipelines
    # (dejar como están hasta completar la Fase 0)
    "tomcat_ami_id": "ami-XXXXXXXXXXXXXXXXX",
    "nginx_ami_id":  "ami-XXXXXXXXXXXXXXXXX",

    # Credenciales de JFrog para descargar el WAR
    "jfrog_user":   "tu@email.com",
    "jfrog_token":  "XXXXXXXXXXXXXXXXX",

    # Launch Templates (Por si se crean de forma independiente antes de desplegar ASGs)
    "tomcat_launch_template_id": "lt-XXXXXXXXXXXXXXXX",  # ⚠️ Reemplaza con tu TomcatLaunchTemplateId
    "nginx_launch_template_id":  "lt-XXXXXXXXXXXXXXXX",  # ⚠️ Reemplaza con tu NginxLaunchTemplateId
}
```

---

## Despliegue paso a paso

```bash
# Obtener los AMI IDs
aws ec2 describe-images \
    --owners self \
    --filters "Name=tag:Project,Values=DevOps-Project-01" \
    --query "Images[*].[Name,ImageId,CreationDate]" \
    --output table \
    --region us-east-1
```

Verás algo como:
```
---------------------------------------------------------------------------
|                          DescribeImages                                 |
+----------------------------+----------------------+---------------------+
|  GlobalAMI-Base-2026-...   |  ami-0abc123def456789 |  2026-03-17T...    |
|  NginxGoldenAMI-2026-...   |  ami-0def456abc789012 |  2026-03-17T...    |
|  TomcatGoldenAMI-2026-...  |  ami-0ghi789def012345 |  2026-03-17T...    |
|  MavenGoldenAMI-2026-...   |  ami-0jkl012ghi345678 |  2026-03-17T...    |
+----------------------------+----------------------+---------------------+
```

Copia los IDs de `NginxGoldenAMI` y `TomcatGoldenAMI` en `app.py`:

```python
"tomcat_ami_id": "ami-0ghi789def012345",   # TomcatGoldenAMI
"nginx_ami_id":  "ami-0def456abc789012",   # NginxGoldenAMI
```

---

### Fase 1 — Infraestructura base

```bash
# Stack 1: VPC, Subnets, IGW, NAT Gateways
cdk deploy NetworkingStack

# Stack 2: Security Groups e IAM Role
cdk deploy SecurityStack

# Stack 3: S3 Bucket y CloudWatch Alarms
# ⚠️ Confirmar el email de SNS cuando llegue el correo de AWS
cdk deploy StorageStack

# Stack 4: RDS MySQL Multi-AZ (~10-15 min)
cdk deploy DatabaseStack
```

---

### Fase 2 — Obtener el endpoint de RDS

```bash
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier prod-mysql \
    --query "DBInstances[0].Endpoint.Address" \
    --output text \
    --region us-east-1)

echo "RDS Endpoint: $RDS_ENDPOINT"
```


Modificar el archivo `DevOps-Project-01/Java-Login-App/src/main/resources/application.properties`
con el $RDS_ENDPOINT,  y el nombre de la base de datos UserDB

y hacer el commit en GitHub (Compilar)
---

### Fase 3 — 

```bash
# Stack 5: Crear los target group

cdk deploy TargetGroupsStack
```

```bash
# Stack 6: Crear los Network Load Balancer
cdk deploy NlbStack
```

### Fase 4 — Obtener el DNS del NLB interno

```bash
PRIVATE_NLB_DNS=$(aws elbv2 describe-load-balancers \
    --names private-nlb \
    --query "LoadBalancers[0].DNSName" \
    --output text \
    --region us-east-1)

echo "Private NLB DNS: $PRIVATE_NLB_DNS"
```

Modificar el archivo o la configuración en el launch template `ngnix-userdata.sh` con el $PRIVATE_NLB_DNS.

---

# Fase 5 - Crear Launch Templates y ASG

```bash
# Crear las launch templates
cdk deploy LaunchTemplateStack
```
En caso de crear las launch templates manualmente, entonces agregar los valores a el area de config en app.py y comentar el ASGStack de la siguiente manera 
```python
asg = ASGStack(
    #...
    #launch_template_nginx=launch_templates.launch_template_nginx,
    launch_template_nginx_id=config["nginx_launch_template_id"],
    #launch_template_tomcat=launch_templates.launch_template_tomcat,
    launch_template_tomcat_id=config["tomcat_launch_template_id"],
    #...
)
```
---

## Despliegue completo (todos los stacks a la vez)

Solo usar después de completar la Fase 0 y tener los AMI IDs en `app.py`.

```bash
# Obtener variables necesarias
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier prod-mysql \
    --query "DBInstances[0].Endpoint.Address" \
    --output text --region us-east-1)

PRIVATE_NLB_DNS=$(aws elbv2 describe-load-balancers \
    --names private-nlb \
    --query "LoadBalancers[0].DNSName" \
    --output text --region us-east-1)

# Desplegar todo
cdk deploy --all \
    -c rds_endpoint=$RDS_ENDPOINT \
    -c private_nlb_dns=$PRIVATE_NLB_DNS
```

---

## Eliminar todos los recursos

```bash
cdk destroy --all
```

> ⚠️ Las AMIs creadas por Image Builder **no se eliminan** con `cdk destroy`. Elimínalas manualmente:
> ```bash
> # Ver AMIs del proyecto
> aws ec2 describe-images --owners self \
>     --filters "Name=tag:Project,Values=DevOps-Project-01" \
>     --query "Images[*].[Name,ImageId]" --output table
>
> # Desregistrar cada AMI y eliminar su snapshot
> aws ec2 deregister-image --image-id ami-XXXXXXXXXXXXXXXXX
> aws ec2 delete-snapshot --snapshot-id snap-XXXXXXXXXXXXXXXXX
> ```

---

## Comandos útiles

```bash
# Ver diferencias antes de aplicar cambios
cdk diff

# Sintetizar CloudFormation sin desplegar
cdk synth

# Listar todos los stacks
cdk list

# Ver outputs de un stack desplegado
aws cloudformation describe-stacks \
    --stack-name NetworkingStack \
    --query "Stacks[0].Outputs" \
    --output table

# Ver estado de todos los stacks
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query "StackSummaries[*].[StackName,StackStatus]" \
    --output table

```

---

## Estructura del proyecto

```
devops-project-01-cdk/
├── app.py                          ← Entrada principal — registra los 7 stacks
├── cdk.json                        ← Configuración del CDK
├── requirements.txt                ← Dependencias Python
├── README.md                       ← Este archivo
└── stacks/
    ├── __init__.py
    ├── imagebuilder_stack.py       ← Stack 0: EC2 Image Builder Pipelines
    ├── networking_stack.py         ← Stack 1: VPC y Networking
    ├── security_stack.py           ← Stack 2: Security Groups + IAM
    ├── storage_stack.py            ← Stack 3: S3 + CloudWatch
    ├── database_stack.py           ← Stack 4: RDS MySQL
    ├── targetgroups_stack.py       ← Stack 5: Target Groups (Nginx + Tomcat)
    ├── nlb_stack.py.               ← Stack 6: Network Load Balancers + Listeners (Nginx + Tomcat)
    ├── templates_stack.py          ← Stack 7: Launch Templates (Nginx + Tomcat)
    ├── asg_stack.py                ← Stack 8: Auto Scaling Groups (Nginx + Tomcat)
    ├── backend_stack.py            ← Stack : Tomcat ASG + NLB interno
    └── frontend_stack.py           ← Stack : Nginx ASG + NLB público
```