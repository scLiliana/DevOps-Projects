#!/usr/bin/env python3
import os
import aws_cdk as cdk

from stacks.networking_stack import NetworkingStack
from stacks.security_stack import SecurityStack
from stacks.bastion_stack import BastionStack
from stacks.storage_stack import StorageStack  
from stacks.launch_template_stack import LaunchTemplateStack
from stacks.alb_stack import ALBStack
from stacks.asg_stack import ASGStack
from stacks.route53_stack import Route53Stack


config = {"your_ip": "0.0.0.0/32",  # Reemplaza con tu IP pública en formato CIDR (ejemplo: 
    
    "region": "us-east-1",  # Reemplaza con tu región preferida

    "global_ami_id": "ami-XXXXXXXXX",  # Reemplaza con el ID de tu Golden AMI
    "key_pair_name": "DevOpsKeyPair",

    "domain_name": "dominio.mx",  # Reemplaza con tu dominio registrado en Route53
}

app = cdk.App()


env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ["CDK_DEFAULT_REGION"],
)

# Stack 1 — VPC y Networking
network = NetworkingStack(app, "NetworkingStack", env=env)

# Stack 2 — Security Groups e IAM
# (Requiere VPC del Stack 1)
security = SecurityStack(
    app, "SecurityStack", 
    vpc=network.vpc,
    bastion_vpc=network.bastion_vpc,
    your_ip=config["your_ip"],  
    env=env)
security.add_dependency(network)  # Asegura que SecurityStack se cree después de NetworkingStack

# Stack 3 — Bastion Host
bastion_stack = BastionStack(
    app, "BastionStack",
    bastion_vpc=network.bastion_vpc,
    bastion_sg=security.bastion_sg,
    key_pair_name=config["key_pair_name"],
    env=env,
)
bastion_stack.add_dependency(network)
bastion_stack.add_dependency(security)

# Stack 4 — Storage (S3 Bucket)
storage_stack = StorageStack(app, "StorageStack", env=env)
storage_stack.add_dependency(network)
storage_stack.add_dependency(security)  

# Stack 5 — Launch Template para ASGs
template_stack = LaunchTemplateStack(
    app, "LaunchTemplateStack",
    vpc=network.vpc,
    appservers_sg=security.appservers_sg,
    global_ami_id=config["global_ami_id"],  # Reemplaza con el ID de tu Golden AMI
    key_pair_name=config["key_pair_name"],
    env=env,
)
template_stack.add_dependency(network)
template_stack.add_dependency(security) 

# Stack 6 — ALB (Requiere VPC, ALB Security Group)
alb_stack = ALBStack(
    app, "ALBStack",
    vpc=network.vpc,
    alb_sg=security.alb_sg,
    env=env, 
)
alb_stack.add_dependency(network)
alb_stack.add_dependency(security)  

# Stack 7 — ASGs y ALB (Requiere VPC, Launch Template, ALB Security Group)
asg_stack = ASGStack( 
    app, "ASGStack",
    vpc=network.vpc,
    launch_template=template_stack.launch_template_app,
    app_tg=alb_stack.app_tg,
    env=env,
)
asg_stack.add_dependency(network)
asg_stack.add_dependency(template_stack)
asg_stack.add_dependency(alb_stack) 

# Stack 8 — Route 53 (Requiere ALB)
route_stack = Route53Stack(
    app, "Route53Stack",
    alb=alb_stack.public_alb,
    domain_name=config["domain_name"],  # Reemplaza con tu dominio
    subdomain="lsccompis",               # Reemplaza con tu subdominio
    env=env,
)
route_stack.add_dependency(alb_stack) 


app.synth()
