from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_autoscaling as autoscaling,
    aws_iam as iam,
)
from constructs import Construct


class NlbStack(Stack):
    """
    Stack — NLB interno para Backend y Nlb público para Frontend
     Crea:
      - NLB interno (private-nlb) con Target Group TCP:8080 (BackendStack)
      - Listener TCP:8080 en el NLB interno
      - NLB público (public-nlb) con Target Group TCP:80 (FrontendStack)
      - Listener TCP:80 en el NLB público
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        tomcat_tg: elbv2.NetworkTargetGroup,
        nginx_tg: elbv2.NetworkTargetGroup, 
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -- NLB interno (backend) ─────────────────────────────────────────────
        self.backend_nlb = elbv2.NetworkLoadBalancer(
            self, "PrivateNLB",
            load_balancer_name="private-nlb",
            vpc=vpc,
            internet_facing=False,
            vpc_subnets=ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
        )

        # Listener TCP:8080 en NLB
        self.backend_nlb.add_listener(
            "TomcatListener",
            port=8080,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[tomcat_tg],
        )

         # ── NLB público (frontend) ────────────────────────────────────────────
        self.public_nlb = elbv2.NetworkLoadBalancer(
            self, "PublicNLB",
            load_balancer_name="public-nlb",
            vpc=vpc,
            internet_facing=True,       # accesible desde internet
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
        )

        # Listener TCP:80
        self.public_nlb.add_listener(
            "NginxListener",
            port=80,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[nginx_tg],
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "PrivateNLBDns",
            value=self.backend_nlb.load_balancer_dns_name,
            description="DNS del NLB interno (backend)",
            export_name="PrivateNLBDns",
        )
        CfnOutput(self, "PublicNLBDns",
            value=self.public_nlb.load_balancer_dns_name,
            description="DNS del NLB público — URL de la aplicación",
            export_name="PublicNLBDns",
        )
        CfnOutput(self, "AppUrl",
            value=f"http://{self.public_nlb.load_balancer_dns_name}",
            description="URL directa a la página de login",
            export_name="AppUrl",
        )