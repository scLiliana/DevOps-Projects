"""
NetworkingStack   → VPC, Subnets, IGW, NAT, Routes

"""

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_logs as logs, 
    aws_iam as iam
)
from constructs import Construct


class NetworkingStack(Stack):
    """
    Stack 1 - VPC y Networking
    Crea:
        VPCs:
            - BastionVPC (172.32.0.0/16)
            - AppVPC (192.168.0.0/16)

        Subnets BastionVPC:
            - 1 Subnet Pública (AZ-1a) -> Bastion Host, IGW

        Subnets AppVPC:
            - 2 Subnets Públicas (AZ-1a, AZ-1b) -> ALB, NAT Gateway
            - 2 Subnets Privadas (AZ-1a, AZ-1b) -> App Servers (ASG)

        Internet Gateways:
            - IGW-BastionVPC -> BastionVPC
            - IGW-AppVPC -> AppVPC

        NAT Gateway:
            - 1 NAT Gateway (AZ-1a, Subnet Pública AppVPC) + EIP

        VPC Peering:
            - PeeringConnection: BastionVPC <-> AppVPC

        Route Tables:
            - RT-Bastion-Public  (0.0.0.0/0 -> IGW-BastionVPC, 192.168.0.0/16 -> PeeringConnection)
            - RT-App-Public      (0.0.0.0/0 -> IGW-AppVPC)
            - RT-App-Private     (0.0.0.0/0 -> NAT Gateway, 172.32.0.0/16 -> PeeringConnection)

        VPC Flow Logs:
            - CloudWatch Log Group: /vpc/flow-logs
                - Log Stream: bastion-vpc-flow-logs
                - Log Stream: app-vpc-flow-logs
            - Flow Log -> BastionVPC -> Log Stream bastion-vpc-flow-logs
            - Flow Log -> AppVPC    -> Log Stream app-vpc-flow-logs
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #-- AppVPC---------------------------------------------
        self.vpc = ec2.Vpc(
            self, "AppVPC",
            vpc_name='AppVPC',
            ip_addresses=ec2.IpAddresses.cidr("192.168.0.0/16"),
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                # Subnets públicas - ALB, NAT Gateway
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=True,
                ),
                # Subnets privadas - App Servers (ASG)
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                )
            ],
        )

        #-- Propiedades de subnets para acceso desde otros stacks ----------------------------------------------
        # Subnets públicas (Load Balancer, NAT Gateway)
        self.public_subnets = self.vpc.public_subnets

        # Subnets privadas (App Servers)
        self.private_subnets = self.vpc.private_subnets

        #-- BastionVPC---------------------------------------------
        self.bastion_vpc = ec2.Vpc(
            self, "BastionVPC",
            vpc_name='BastionVPC',
            ip_addresses=ec2.IpAddresses.cidr("172.32.0.0/16"),
            max_azs=1,
            subnet_configuration=[
                # Subnets públicas - Bastion Host, IGW
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=True,
                )
            ],
        )

        # #-- Transit Gateway ---------------------------------------------
        # tgw = ec2.CfnTransitGateway(self, "TransitGateway",
        #     description="TGW BastionVPC <-> AppVPC",
        #     amazon_side_asn=64512,
        #     auto_accept_shared_attachments="enable",
        #     tags=[{"key": "Name", "value": "TransitGateway"}]
        # )
        # tgw_attachment_app = ec2.CfnTransitGatewayAttachment(self, "TGWAttachmentApp",
        #     transit_gateway_id=tgw.ref,
        #     vpc_id=self.vpc.vpc_id,
        #     subnet_ids=[s.subnet_id for s in self.private_subnets],
        # )
        # tgw_attachment_bastion = ec2.CfnTransitGatewayAttachment(self, "TGWAttachmentBastion",
        #     transit_gateway_id=tgw.ref,
        #     vpc_id=self.bastion_vpc.vpc_id,
        #     subnet_ids=[self.bastion_vpc.public_subnets[0].subnet_id],
        # )


        # #-- Routes ---------------------------------------------
        # # Ruta en Bastion Public: 192.168.0.0/16 -> TGW
        # ec2.CfnRoute(self, "BastionToAppViaTGW",
        #     route_table_id=self.bastion_vpc.public_subnets[0].route_table.route_table_id,
        #     destination_cidr_block="192.168.0.0/16",
        #     transit_gateway_id=tgw.ref,
        # ).add_dependency(tgw_attachment_bastion)

        # # Ruta en App Private: 172.32.0.0/16 -> TGW
        # for i, subnet in enumerate(self.private_subnets):
        #     ec2.CfnRoute(self, f"AppPrivateToBasionViaTGW{i}",
        #         route_table_id=subnet.route_table.route_table_id,
        #         destination_cidr_block="172.32.0.0/16",
        #         transit_gateway_id=tgw.ref,
        #     ).add_dependency(tgw_attachment_app)

        #-- VPC Peering ---------------------------------------------
        peering_connection = ec2.CfnVPCPeeringConnection(
            self, "BastionAppPeering",
            vpc_id=self.vpc.vpc_id,               # Accepter: AppVPC
            peer_vpc_id=self.bastion_vpc.vpc_id,  # Requester: BastionVPC
            # peer_owner_id=self.account,  # Opcional si ambas VPCs están en la misma cuenta
            # peer_region=self.region,  # Opcional si ambas VPCs están en la misma región
            tags=[{"key": "Name", "value": "BastionVPC-AppVPC-Peering"}]
        )

        #-- Routes ---------------------------------------------
        # Ruta en Bastion Public: 192.168.0.0/16 -> Peering
        # NOTA: Logical ID igual al original (TGW) para que CF haga UPDATE y no CREATE
        ec2.CfnRoute(
            self, "BastionToAppViaTGW",
            route_table_id=self.bastion_vpc.public_subnets[0].route_table.route_table_id,
            destination_cidr_block="192.168.0.0/16",
            vpc_peering_connection_id=peering_connection.ref,
        )
 
        # Ruta en App Private: 172.32.0.0/16 -> Peering
        # NOTA: Logical IDs iguales a los originales (TGW) para que CF haga UPDATE y no CREATE
        for i, subnet in enumerate(self.private_subnets):
            ec2.CfnRoute(
                self, f"AppPrivateToBasionViaTGW{i}",  # typo "Basion" intencional: idéntico al original
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block="172.32.0.0/16",
                vpc_peering_connection_id=peering_connection.ref,
            )

        #-- VPC Flow Logs ----------------------------------------------
        log_group = logs.LogGroup(self, "VpcFlowLogsGroup",
            log_group_name="/vpc/flow-logs",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        flow_log_role = iam.Role(self, "FlowLogRole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )
        log_group.grant_write(flow_log_role)

        self.vpc.add_flow_log("AppVpcFlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group, flow_log_role),
            traffic_type=ec2.FlowLogTrafficType.REJECT,
        )
        self.bastion_vpc.add_flow_log("BastionVpcFlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group, flow_log_role),
            traffic_type=ec2.FlowLogTrafficType.REJECT,
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

        CfnOutput(self, "BastionVpcId",
            value=self.bastion_vpc.vpc_id,
            description="ID de la VPC del Bastion Host",
            export_name="BastionVPCId",
        )
        CfnOutput(self, "BastionPublicSubnet1a",
            value=self.bastion_vpc.public_subnets[0].subnet_id,
            description="Subnet pública AZ-1a del Bastion Host",
            export_name="BastionPublicSubnet1aId",
        ) 


