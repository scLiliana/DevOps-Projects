"""
NetworkingStack   → VPC, Subnets, IGW, NAT, Routes

"""

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
)
from constructs import Construct


class NetworkingStack(Stack):
    """
    Stack 1 - VPC y Networking
    Crea:
        - PrimaryVPC (192.168.0.0/16)
        - 2 Subnets Publicas (AZ-1a, AZ-1b) -> Bastion, NAT, NLB público
        - 2 Subnets Privadas (AZ-1a, AZ-1b) -> Nginx, Tomcat
        - 2 Subnets de BD (AZ-1a, AZ-1b) -> RDS MySQL
        - Internet Gateway
        - 2 NAT Gateway (AZ-1a, AZ-1b)
        - Route Tables (pública -> IGW, privadas -> NAT respectivo)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #-- VPC----------------------------------------------
        self.vpc = ec2.Vpc(
            self, "PrimaryVPC",
            vpc_name='PrimaryVPC',
            ip_addresses=ec2.IpAddresses.cidr("192.168.0.0/16"),
            max_azs=2,
            nat_gateways=2,
            subnet_configuration=[
                # Subnets públicas - Bastion, NAT Gateways, NLB público
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=True,
                ),
                # Subnets privadas - Nginx ASG, Tomcat ASG, NBL privado
                ec2.SubnetConfigurartion(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                # Subnets de BD - RDS MySQL (sin salida a internet)
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                )
            ],
        )

        #-- Propiedades de subnets para acceso desde otros stacks ----------------------------------------------
        # Subnets públicas
        self.public_subnets = self.vpc.public_subnets

        # Subnets privadas (Nginx + Tomcat)
        self.private_subnets = self.vpc.private_subnets

        #Subnets de base de datos (RDS)
        self.isolated_subnets = self.vpc.isolated_subnets

        #-- VPC Flow Logs ----------------------------------------------
        self.vpc.add_flow_log(
            "VpcFlowLog",
            destination = ec2.FlowLogaDestination.to_cloud_watch_logs(),
            traffic_type = ec2.FlowLogTrafficType.REJECT,
        )

        #-- Outputs ----------------------------------------------
        CfnOutput(self, "VpcId",
            value = self.vpc.vpc_id,
            description = "ID de la VPC principal",
            export_name = "PrimaryVPCId",
        )

        CfnOutput(self, "PublicSubnet1a",
            value=self.public_subnets[0].subnet_id,
            description="Subnet pública AZ-1a",
            export_name="PublicSubnet1aId",
        )

        CfnOutput(self, "PublicSubnet1b",
            value=self.public_subnets[1].subnet_id,
            description="Subnet pública AZ-1b",
            export_name="PublicSubnet1bId",
        )

        CfnOutput(self, "PrivateSubnet1a",
            value=self.private_subnets[0].subnet_id,
            description="Subnet privada AZ-1a Ngnix/Tomcat",
            export_name="PrivateSubnet1aId",
        )

        CfnOutput(self, "PrivateSubnet1b",
            value=self.private_subnets[1].subnet_id,
            description="Subnet privada AZ-1b Ngnix/Tomcat",
            export_name="PrivateSubnet1bId",
        )

        CfnOutput(self, "DatabaseSubnet1a",
            value=self.isolated_subnets[0].subnet_id,
            description="Subnet de base de datos AZ-1a RDS",
            export_name="DatabaseSubnet1aId",
        )

        CfnOutput(self, "DatabaseSubnet1b",
            value=self.isolated_subnets[1].subnet_id,
            description="Subnet de base de datos AZ-1b RDS",
            export_name="DatabaseSubnet1bId",
        )
