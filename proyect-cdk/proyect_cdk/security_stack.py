"""
SecurityStack     → Security Groups + IAM Role

"""

from aws_cdk import (
    Stack,
    CfnOutput, 
    aws_ec2 as ec2,
    aws_iam as iam, 
)

from constructs import Construct 

class SecurityStack(Stack):
    """
    Stack 2 - Security Groups y IAM Role
    Crea:
        - BastionSG -> SSH desde tu IP
        - FrontendSG -> HTTP/HTTPS desde internet, SSH desde BastionSG
        - BackendSG -> Puerto 8080 dede FrontendSG, SSH desde BastionSG
        - DatabaseSG -> Puerto 3306 desde BackendSG y BastionSG
        - IAM Role EC2AppRole -> Instance Profile EC2AppProfile
    """

    def __init__(
            self,
            scope: Construct,
            contruct_id: str,
            vpc: ec2.Vpc,
            your_ip: str,
            **kwargs
    ) -> None:
        super().__init__(scope, contruct_id, **kwargs)


        #-- BastionSG - SHH solo desde tu IP ------------------------

        self.bastion_sg = ec2.SecurityGroup(
            self, "BastionSG",
            security_group_name="BastionSG",
            vpc=vpc,
            description="SSH access to Bastion Host form admin IP only",
            allow_all_outbound=True,
        )
        self.bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(your_ip),
            connection=ec2.Port.tcp(22),
            description="SSH desde IP del administrador"
        )

        # ── FrontendSG — Nginx ────────────────────────────────────────────────
        self.frontend_sg = ec2.SecurityGroup(
            self, "FrontendSG",
            security_group_name="FrontendSG",
            vpc=vpc,
            description="Security Group for Nginx frontend servers",
            allow_all_outbound=True,
        )
        # HTTP desde internet
        self.frontend_sg.add_ingress_rule(
            peer = ec2.Peer.any_ipv4(),
            connection= ec2.Port.tcp(80),
            description="HTTP desde internet"
        )
        # HTTPS desde internet
        self.frontend_sg.add_ingress_rule(
            peer = ec2.Peer.any_ipv4(),
            connection= ec2.Port.tcp(443),
            description="HTTPS desde internet"
        )
        # SSH desde BastionSG
        self.frontend_sg.add_ingress_rule(
            peer = self.bastion_sg,
            connection = ec2.Port.tcp(22),
            description="SSH desde BastionSG"
        )   

        # ── BackendSG — Tomcat ────────────────────────────────────────────────
        self.bastion_sg = ec2.SecurityGroup(
            self, "BackendSG",
            security_group_name="BackendSG",
            vpc=vpc,
            description="Security Group for Tomcat backend servers",
            allow_all_outbound=True,
        )

        # Puerto 8080 solo desde FrontendSG
        self.bastion_sg.add_ingress_rule(
            peer = self.frontend_sg,
            connection = ec2.Port.tcp(8080),
            description="Tomcat desde Nginx (FrontendSG)",
        )

        # Puerto 8080 desde toda la VPC (para el NLB interno)
        self.backend_sg.add_ingress_rule(
            peer=self.frontend_sg,
            connection=ec2.Port.tcp(8080),
            description="Tomcat desde VPC (para NLB interno)",
        )

        # SSH desde BastionSG
        self.backend_sg.add_ingress_rule(
            peer = self.bastion_sg,
            connection=ec2.Port.tcp(22),
            description="SSH desde Bastion",
        )


        # ── DatabaseSG — RDS MySQL ────────────────────────────────────────────────
        self.database_sg = ec2.SecurityGroup(
            self, "DatabaseSG",
            security_group_name="DatabaseSG",
            vpc=vpc,
            description="Security Group for MySQL RDS",
            allow_all_outbound=True,
        )

        # MySQL desde BackendSG (instancias Tomcat)
        self.database_sg.add_ingress_rule(
            peer = self.backend_sg,
            connection = ec2.Port.tcp(3306),
            description="MySQL desde Tomcat (BackendSG)",
        )

        # MySQL desde BastionSG (administración)
        self.database_sg.add_ingress_rule(
            peer=self.bastion_sg,
            connection=ec2.Port.tcp(3306),
            description="MySQL desde BastionSG (administración)",
        )

        # ── IAM Role para instancias EC2 ──────────────────────────────────────
        self.ec2_role = iam.Role(
            self, "EC2AppRole",
            role_name="EC2AppRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Role para instancias Nginx y Tomcat",
            managed_policies=[
                # SSM - acceso sin SSH
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                    ),
                    # CloudWatch Logs - para enviar métricas y logs
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchAgentServerPolicy"
                ),
            ],
        )

        # Política personalizada para acceso a S3 (logs de Tomcat)
        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3LogsAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:DeleteObject"
                ],
                resources=[
                    "arn:aws:s3:::devops-project-01-logs-*",
                    "arn:aws:s3:::devops-project-01-logs-*/*"
                ],
            )
        )

        # Política para descargar artefactos desde S3 (War files)
        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRAndArtifactAccess",
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::*"],
            )
        )
        
        # Instance Profile - wrapper del Role para asignarlo a EC2
        self.instance_profile = iam.CfnInstanceProfile(
            self, "EC2AppProfile",
            instance_profile="EC2AppProfile",
            roles=[self.ec2_role.role_name],
        )

        # -- Outputs --------------------------------------

        CfnOutput(self, "BastionSGId", 
            value=self.bastion_sg.security_group_id, 
            description="ID del BastionSG",
            export_name="BastionSGId"
            )
        
        CfnOutput(self, "FrontendSGId",
            value=self.frontend_sg.security_group_id,
            description="ID del FrontendSG",
            export_name="FrontendSGId"
        )
        CfnOutput(self, "BackendSGId",
            value=self.backend_sg.security_group_id,
            description="ID del BackendSG",
            export_name="BackendSGId"
        )
        CfnOutput(self, "DatabaseSGId",
            value=self.database_sg.security_group_id,
            description="ID del DatabaseSG",
            export_name="DatabaseSGId"
        )
        CfnOutput(self, "EC2RoleArn",
            value=self.ec2_role.role_arn,
            description="ARN del IAM Role para EC2",
            export_name="EC2AppRoleArn"
        )
        CfnOutput(self, "EC2InstanceProfileName",
            value=self.instance_profile.instance_profile_name,
            description="Nombre del Instance Profile",
            export_name="EC2AppProfileName"
        )