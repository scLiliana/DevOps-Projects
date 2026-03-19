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

class ASGStack(Stack):
    """
    Stack — ASGs para Tomcat y Nginx
    Crea:
      - Auto Scaling Group para Tomcat (BackendStack) con Launch Template
      - Auto Scaling Group para Nginx (FrontendStack) con Launch Template
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        launch_template_nginx: ec2.CfnLaunchTemplate,
        launch_template_tomcat: ec2.CfnLaunchTemplate,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Auto Scaling Group Nginx ────────────────────────────────────────────────
        self.nginx_asg = autoscaling.AutoScalingGroup(
            self, "NginxASG",
            auto_scaling_group_name="nginx-asg",
            vpc=vpc,
            launch_template=launch_template_nginx,
            min_capacity=1,
            max_capacity=3,
            desired_capacity=2,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            health_checks=autoscaling.HealthChecks.ec2(
                grace_period=Duration.minutes(5)
            ),
        )

        # Registrar el ASG en el Target Group
        self.nginx_asg.attach_to_network_target_group(self.nginx_tg)

        # Scaling policy — escalar cuando CPU > 70%
        self.nginx_asg.scale_on_cpu_utilization(
            "NginxCPUScaling",
            target_utilization_percent=70,
        )

        # ── Auto Scaling Group Tomcat ────────────────────────────────────────────────
        self.tomcat_asg = autoscaling.AutoScalingGroup(
            self, "TomcatASG",
            auto_scaling_group_name="tomcat-asg",
            vpc=vpc,
            launch_template=launch_template_tomcat,
            min_capacity=1,
            max_capacity=3,
            desired_capacity=2,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            health_checks=autoscaling.HealthChecks.ec2(
                grace_period=Duration.minutes(5)
            ),
        )

            # Registrar ASG en Target Group
        self.tomcat_asg.attach_to_network_target_group(self.tomcat_tg)

            # Scaling policy - escalar cuando CPU > 70%
        self.tomcat_asg.scale_on_cpu_utilization(
            "TomcatCPUScaling",
            target_utilization_percent=70,
        )