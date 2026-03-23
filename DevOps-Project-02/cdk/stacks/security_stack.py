from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct


class SecurityStack(Stack):
    """
    Crea:
        Security Groups:
            - BastionSG    (Inbound: TCP 22 -> 0.0.0.0/0)
            - AlbSG        (Inbound: TCP 80, 443 -> 0.0.0.0/0)
            - AppServersSG  (Inbound: TCP 22 -> BastionSG, TCP 80 -> AlbSG)
        
        IAM:
            - IAM Role: AppServerRole
                - Policy: AmazonSSMManagedInstanceCore (Session Manager)
                - Policy inline: S3 GetObject -> app-config-bucket (sin S3 Full Access)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        bastion_vpc: ec2.Vpc,
        your_ip: str,   # Tu IP pública en formato "X.X.X.X/32"
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── BastionSG — SSH solo desde tu IP ──────────────────────────────────
        self.bastion_sg = ec2.SecurityGroup(
            self, "BastionSG",
            security_group_name="BastionSG",
            vpc=bastion_vpc,
            description="SSH access to Bastion Host from admin IP only",
            allow_all_outbound=True,
        )
        self.bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(your_ip),
            connection=ec2.Port.tcp(22),
            description="SSH from admin IP",
        )

        # -- ALB Security Group (para permitir tráfico HTTP/HTTPS desde internet) ───────────────────────────────
        self.alb_sg = ec2.SecurityGroup(
            self, "AlbSG",
            security_group_name="AlbSG",
            vpc=vpc,
            description="Security group for Application Load Balancer",
            allow_all_outbound=True,
        )
        # self.alb_sg.add_ingress_rule(
        #     peer=ec2.Peer.any_ipv4(),
        #     connection=ec2.Port.tcp(80),
        #     description="HTTP desde internet",
        # )
        # self.alb_sg.add_ingress_rule(
        #     peer=ec2.Peer.any_ipv4(),
        #     connection=ec2.Port.tcp(443),
        #     description="HTTPS desde internet",
        # )
        cloudflare_ip_ranges = [
            "173.245.48.0/20",
            "103.21.244.0/22",
            "103.22.200.0/22",
            "103.31.4.0/22",
            "141.101.64.0/18",
            "108.162.192.0/18", 
            "190.93.240.0/20",
            "188.114.96.0/20",
            "197.234.240.0/22",
            "198.41.128.0/17",
            "162.158.0.0/15",
            "104.16.0.0/13",
            "104.24.0.0/14",
            "172.64.0.0/13",
            "131.0.72.0/22",
        ]

        for ip_range in cloudflare_ip_ranges:
            self.alb_sg.add_ingress_rule(
                peer=ec2.Peer.ipv4(ip_range),
                connection=ec2.Port.tcp(80),
                description=f"HTTP desde Cloudflare IP {ip_range}",
            )
            self.alb_sg.add_ingress_rule(
                peer=ec2.Peer.ipv4(ip_range),
                connection=ec2.Port.tcp(443),
                description=f"HTTPS desde Cloudflare IP {ip_range}",
            )
    
        # ── AppServersSG  ────────────────────────────────────────────────
        self.appservers_sg = ec2.SecurityGroup(
            self, "AppServersSG",
            security_group_name="AppServersSG",
            vpc=vpc,
            description="Security group for application servers",
            allow_all_outbound=True,
        )
        # HTTP desde ALB (dentro de AppVPC)
        self.appservers_sg.add_ingress_rule(
            peer=self.alb_sg, 
            connection=ec2.Port.tcp(80),
            description="HTTP desde ALB (dentro de AppVPC)",
        )
        # SSH desde Bastion
        self.appservers_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(bastion_vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(22),
            description="SSH desde Bastion VPC via VPC Peering",
        )
        # ── IAM Role ──────────────────────────────────────
        self.ec2_role = iam.Role(
            self, "AppServerRole",
            role_name="AppServerRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Role for application servers with SSM access and S3 logs permissions",
            managed_policies=[
                # SSM — acceso sin SSH
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
        )

        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowReadAccessToSpecificS3Bucket",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation"
                ],
                resources=[
                    f"arn:aws:s3:::app-config-bucket-{self.account}",
                    f"arn:aws:s3:::app-config-bucket-{self.account}/*",
                ],
            )
        )

        # ── Outputs ───────────────────────────────────────────
        CfnOutput(self, "EC2RoleArn",
            value=self.ec2_role.role_arn,
            description="AppServer IAM Role ARN",
            export_name="AppServerRoleArn",
        )

        CfnOutput(self, "BastionSGId",
            value=self.bastion_sg.security_group_id,
            description="BastionSG ID",
            export_name="BastionSGId",
        )
    
        CfnOutput(self, "AppServersSGId",
            value=self.appservers_sg.security_group_id,
            description="AppServersSG ID",
            export_name="AppServersSGId",
        )
