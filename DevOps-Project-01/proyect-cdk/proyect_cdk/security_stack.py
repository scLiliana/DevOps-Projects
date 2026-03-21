from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct


class SecurityStack(Stack):
    """
    Stack 2 — Security Groups e IAM
    Crea:
      - BastionSG    → SSH desde tu IP únicamente
      - FrontendSG   → HTTP/HTTPS desde internet, SSH desde Bastion
      - BackendSG    → Puerto 8080 desde FrontendSG, SSH desde Bastion
      - DatabaseSG   → Puerto 3306 desde BackendSG y BastionSG
      - IAM Role EC2AppRole + Instance Profile EC2AppProfile
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        your_ip: str,   # Tu IP pública en formato "X.X.X.X/32"
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── BastionSG — SSH solo desde tu IP ──────────────────────────────────
        self.bastion_sg = ec2.SecurityGroup(
            self, "BastionSG",
            security_group_name="BastionSG",
            vpc=vpc,
            description="SSH access to Bastion Host from admin IP only",
            allow_all_outbound=True,
        )
        self.bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(your_ip),
            connection=ec2.Port.tcp(22),
            description="SSH from admin IP",
        )

        # ── FrontendSG — Nginx ────────────────────────────────────────────────
        self.frontend_sg = ec2.SecurityGroup(
            self, "FrontendSG",
            security_group_name="FrontendSG",
            vpc=vpc,
            description="Security group for Nginx frontend servers",
            allow_all_outbound=True,
        )
        # HTTP desde internet
        self.frontend_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="HTTP from internet",
        )
        # HTTPS desde internet
        self.frontend_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS from internet",
        )
        # SSH desde Bastion
        self.frontend_sg.add_ingress_rule(
            peer=self.bastion_sg,
            connection=ec2.Port.tcp(22),
            description="SSH from Bastion",
        )

        # ── BackendSG — Tomcat ────────────────────────────────────────────────
        self.backend_sg = ec2.SecurityGroup(
            self, "BackendSG",
            security_group_name="BackendSG",
            vpc=vpc,
            description="Security group for Tomcat backend servers",
            allow_all_outbound=True,
        )
        # Puerto 8080 solo desde FrontendSG
        self.backend_sg.add_ingress_rule(
            peer=self.frontend_sg,
            connection=ec2.Port.tcp(8080),
            description="Tomcat from Nginx FrontendSG",
        )
        # Puerto 8080 desde toda la VPC (para el NLB interno)
        self.backend_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(8080),
            description="Tomcat from VPC internal NLB",
        )
        # SSH desde Bastion
        self.backend_sg.add_ingress_rule(
            peer=self.bastion_sg,
            connection=ec2.Port.tcp(22),
            description="SSH from Bastion",
        )

        # ── DatabaseSG — RDS MySQL ────────────────────────────────────────────
        self.database_sg = ec2.SecurityGroup(
            self, "DatabaseSG",
            security_group_name="DatabaseSG",
            vpc=vpc,
            description="Security group for MySQL RDS",
            allow_all_outbound=True,
        )
        # MySQL desde BackendSG (instancias Tomcat)
        self.database_sg.add_ingress_rule(
            peer=self.backend_sg,
            connection=ec2.Port.tcp(3306),
            description="MySQL from Tomcat BackendSG",
        )
        # MySQL desde BastionSG (administración)
        self.database_sg.add_ingress_rule(
            peer=self.bastion_sg,
            connection=ec2.Port.tcp(3306),
            description="MySQL from Bastion admin",
        )

        # ── IAM Role para instancias EC2 ──────────────────────────────────────
        self.ec2_role = iam.Role(
            self, "EC2AppRole",
            role_name="EC2AppRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Role for Nginx and Tomcat instances",
            managed_policies=[
                # SSM — acceso sin SSH
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
                # CloudWatch — enviar métricas y logs
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchAgentServerPolicy"
                ),
            ],
        )

        # Política personalizada para S3 (logs de Tomcat)
        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3LogsAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:DeleteObject",
                ],
                resources=[
                    f"arn:aws:s3:::devops-project-01-logs-*",
                    f"arn:aws:s3:::devops-project-01-logs-*/*",
                ],
            )
        )

        # Política para descargar artefactos desde S3 (WAR files)
        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRAndArtifactsAccess",
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::*"],
            )
        )

        # Instance Profile — wrapper del Role para asignarlo a EC2
        self.instance_profile = iam.CfnInstanceProfile(
            self, "EC2AppProfile",
            instance_profile_name="EC2AppProfile",
            roles=[self.ec2_role.role_name],
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "BastionSGId",
            value=self.bastion_sg.security_group_id,
            description="BastionSG ID",
            export_name="BastionSGId",
        )
        CfnOutput(self, "FrontendSGId",
            value=self.frontend_sg.security_group_id,
            description="FrontendSG ID",
            export_name="FrontendSGId",
        )
        CfnOutput(self, "BackendSGId",
            value=self.backend_sg.security_group_id,
            description="BackendSG ID",
            export_name="BackendSGId",
        )
        CfnOutput(self, "DatabaseSGId",
            value=self.database_sg.security_group_id,
            description="DatabaseSG ID",
            export_name="DatabaseSGId",
        )
        CfnOutput(self, "EC2RoleArn",
            value=self.ec2_role.role_arn,
            description="EC2 IAM Role ARN",
            export_name="EC2AppRoleArn",
        )
        CfnOutput(self, "EC2InstanceProfileName",
            value=self.instance_profile.instance_profile_name,
            description="Instance Profile name",
            export_name="EC2AppProfileName",
        )