from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct


class ALBStack(Stack):
    """
    Stack — ALB público para Frontend
     Crea:
     
        Load Balancer:
            - Target Group (HTTP, asociado al ASG)
            - Application Load Balancer (Subnets Públicas AppVPC)
                - Listener HTTP:80 -> Target Group
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        alb_sg: ec2.SecurityGroup,
        #certificate_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Target Group ─────────────────────────────────────────────────────
        self.app_tg = elbv2.ApplicationTargetGroup(
            self, "AppTG",
            target_group_name="app-tg",
            vpc=vpc,
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                protocol=elbv2.Protocol.HTTP,
                path="/health",
                port="80",
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
            ),
        )

        # ── ALB ───────────────────────────────────────────────────────────────
        self.public_alb = elbv2.ApplicationLoadBalancer(
            self, "PublicALB",
            load_balancer_name="public-alb",
            vpc=vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),
            security_group=alb_sg,
        )

        # Listener HTTP:80 
        self.public_alb.add_listener(
            "HttpListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[self.app_tg],
        )

        # # Listener HTTPS:443 — tráfico real
        # self.public_alb.add_listener(
        #     "HttpsListener",
        #     port=443,
        #     protocol=elbv2.ApplicationProtocol.HTTPS,
        #     certificates=[elbv2.ListenerCertificate.from_arn(certificate_arn)],
        #     default_target_groups=[self.app_tg],
        # )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "AppTGArn",
            value=self.app_tg.target_group_arn,
            export_name="AppTGArn",
        )
        CfnOutput(self, "PublicALBDns",
            value=self.public_alb.load_balancer_dns_name,
            description="DNS del ALB público",
            export_name="PublicALBDns",
        )