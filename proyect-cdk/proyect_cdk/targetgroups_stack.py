from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct

class TargetGroupsStack(Stack):
    """
    Stack — Target Groups: Tomcat y Nginx
    Crea:
      - Target Group TCP:8080 para Tomcat
      - Target Group TCP:80 para Nginx
    """

    def __init__(
            self, 
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            **kwargs
        ) -> None:
            super().__init__(scope, construct_id, **kwargs)

            # Target Group TCP:8080 para Tomcat
            self.tomcat_tg = elbv2.NetworkTargetGroup(      # ← Application → Network
                self, "TomcatTG",
                target_group_name="tomcat-tg",
                vpc=vpc,
                port=8080,
                protocol=elbv2.Protocol.TCP,
                target_type=elbv2.TargetType.INSTANCE,
                health_check=elbv2.HealthCheck(
                    protocol=elbv2.Protocol.TCP,
                    port="8080",
                    healthy_threshold_count=2,
                    unhealthy_threshold_count=2,
                    interval=Duration.seconds(30),
                ),
            )
        # ── Target Group TCP:80 ───────────────────────────────────────────────
            self.nginx_tg = elbv2.NetworkTargetGroup(
                self, "NginxTG",
                target_group_name="nginx-tg",
                vpc=vpc,
                port=80,
                protocol=elbv2.Protocol.TCP,
                target_type=elbv2.TargetType.INSTANCE,
                health_check=elbv2.HealthCheck(
                    protocol=elbv2.Protocol.TCP,
                    port="80",
                    healthy_threshold_count=2,
                    unhealthy_threshold_count=2,
                    interval=Duration.seconds(30),
                ),
            )

            # -- Outputs ───────────────────────────────────────────────────────────────

            CfnOutput(self, "TomcatTGArn",
                value=self.tomcat_tg.target_group_arn,
                description="ARN del Target Group de Tomcat",
                export_name="TomcatTGArn",
            )
            CfnOutput(self, "NginxTGArn",
                value=self.nginx_tg.target_group_arn,
                description="ARN del Target Group de Nginx",
                export_name="NginxTGArn",
            )