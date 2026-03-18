#!/usr/bin/env python3
"""
DevOps Project-01 — CDK App
Despliega la arquitectura 3-tier en AWS:
  Internet → NLB público → Nginx ASG → NLB privado → Tomcat ASG → RDS MySQL

Orden de despliegue:
  1. NetworkingStack   → VPC, Subnets, IGW, NAT, Routes
  2. SecurityStack     → Security Groups + IAM Role
  3. StorageStack      → S3 Bucket + CloudWatch Alarms
  4. DatabaseStack     → RDS MySQL Multi-AZ
  5. BackendStack      → Tomcat ASG + NLB interno
  6. FrontendStack     → Nginx ASG + NLB público

USO:
  # Instalar dependencias
  pip install -r requirements.txt

  # Verificar cuenta y región configuradas
  aws sts get-caller-identity

  # Sintetizar CloudFormation (verificar sin desplegar)
  cdk synth

  # Desplegar todos los stacks en orden
  cdk deploy --all

  # Desplegar un stack específico
  cdk deploy NetworkingStack

  # Ver diferencias antes de desplegar
  cdk diff

  # Eliminar todos los recursos
  cdk destroy --all
"""

import aws_cdk as cdk

from proyect_cdk.imagebuilder_stack import ImageBuilderStack
from proyect_cdk.networking_stack import NetworkingStack
from proyect_cdk.security_stack import SecurityStack
from proyect_cdk.storage_stack import StorageStack
from proyect_cdk.database_stack import DatabaseStack
from proyect_cdk.backend_stack import BackendStack
from proyect_cdk.frontend_stack import FrontendStack

# ── CONFIGURACIÓN — edita estos valores antes de desplegar ────────────────────
config = {
    # Tu IP pública en formato CIDR (para acceso SSH al Bastion)
    # Obtenerla con: curl https://checkip.amazonaws.com
    "your_ip": "0.0.0.0/0",            # ⚠️ Reemplaza con tu IP real: "X.X.X.X/32"

    # Email para recibir alertas de CloudWatch
    "alert_email": "tu@email.com",      # ⚠️ Reemplaza con tu email real

    # Contraseña del usuario admin de RDS
    "db_password": "TuPasswordSegura123!",  # ⚠️ Cambia esto

    # IDs de las Golden AMIs creadas en el Paso 2
    # Obtenerlos con: aws ec2 describe-images --owners self --query "Images[*].[Name,ImageId]"
    "tomcat_ami_id": "ami-XXXXXXXXXXXXXXXXX",   # ⚠️ Reemplaza con tu TomcatGoldenAMI
    "nginx_ami_id":  "ami-XXXXXXXXXXXXXXXXX",   # ⚠️ Reemplaza con tu NginxGoldenAMI

    # Credenciales de JFrog para descargar el WAR
    "jfrog_user":  "tu@email.com",      # ⚠️ Reemplaza con tu email de JFrog
    "jfrog_token": "XXXXXXXXXXXXXXXXX", # ⚠️ Reemplaza con tu Access Token de JFrog

    # Región y cuenta AWS
    "region": "us-east-1",
}

# ── CDK App ───────────────────────────────────────────────────────────────────
app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,  # usa la cuenta del CLI
    region=config["region"],
)

# Stack 0 — EC2 Image Builder (Golden AMIs)
# Después de desplegarlo, ejecutar los pipelines manualmente en la consola AWS
# y anotar los AMI IDs resultantes en el bloque config de arriba
image_builder = ImageBuilderStack(app, "ImageBuilderStack", env=env)

# Stack 1 — VPC y Networking
networking = NetworkingStack(app, "NetworkingStack", env=env)

# Stack 2 — Security Groups e IAM
security = SecurityStack(
    app, "SecurityStack",
    vpc=networking.vpc,
    your_ip=config["your_ip"],
    env=env,
)
security.add_dependency(networking)

# Stack 3 — S3 y CloudWatch
storage = StorageStack(
    app, "StorageStack",
    alert_email=config["alert_email"],
    env=env,
)
storage.add_dependency(security)

# Stack 4 — RDS MySQL
database = DatabaseStack(
    app, "DatabaseStack",
    vpc=networking.vpc,
    database_sg=security.database_sg,
    db_password=config["db_password"],
    env=env,
)
database.add_dependency(security)

# Stack 5 — Tomcat ASG + NLB interno
# ⚠️ Requiere el endpoint de RDS — se obtiene después de desplegar DatabaseStack
# Si despliegas por primera vez usa: cdk deploy NetworkingStack SecurityStack StorageStack DatabaseStack
# Luego obtén el endpoint con: aws rds describe-db-instances --db-instance-identifier prod-mysql --query "DBInstances[0].Endpoint.Address" --output text
rds_endpoint = app.node.try_get_context("rds_endpoint") or "PENDING"

backend = BackendStack(
    app, "BackendStack",
    vpc=networking.vpc,
    backend_sg=security.backend_sg,
    instance_profile=security.instance_profile,
    tomcat_ami_id=config["tomcat_ami_id"],
    jfrog_user=config["jfrog_user"],
    jfrog_token=config["jfrog_token"],
    rds_endpoint=rds_endpoint,
    db_password=config["db_password"],
    env=env,
)
backend.add_dependency(database)

# Stack 6 — Nginx ASG + NLB público
# ⚠️ Requiere el DNS del NLB interno — se obtiene después de desplegar BackendStack
# Obtenerlo con: aws elbv2 describe-load-balancers --names private-nlb --query "LoadBalancers[0].DNSName" --output text
private_nlb_dns = app.node.try_get_context("private_nlb_dns") or "PENDING"

frontend = FrontendStack(
    app, "FrontendStack",
    vpc=networking.vpc,
    frontend_sg=security.frontend_sg,
    instance_profile=security.instance_profile,
    nginx_ami_id=config["nginx_ami_id"],
    private_nlb_dns=private_nlb_dns,
    env=env,
)
frontend.add_dependency(backend)

app.synth()