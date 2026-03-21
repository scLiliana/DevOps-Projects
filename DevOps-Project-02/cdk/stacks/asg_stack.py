from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_autoscaling as autoscaling,
)
from constructs import Construct

class ASGStack(Stack):
    """
    Stack — ASGs 
    Crea:
        Auto Scaling:
        - Auto Scaling Group
            - Min: 2, Max: 4
            - Subnets: 2 Subnets Privadas (AZ-1a, AZ-1b)
            - Launch Template: LaunchTemplate
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        launch_template: ec2.LaunchTemplate, 
        app_tg: elbv2.ApplicationTargetGroup,         
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Auto Scaling App ────────────────────────────────────────────────
        self.app_asg = autoscaling.AutoScalingGroup(
            self, "AppASG",
            auto_scaling_group_name="app-asg",
            vpc=vpc,
            launch_template=launch_template,
            min_capacity=2,
            max_capacity=4,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            health_checks=autoscaling.HealthChecks.ec2(
                grace_period=Duration.minutes(5)
            ),
            update_policy=autoscaling.UpdatePolicy.rolling_update(
                max_batch_size=1,
                min_instances_in_service=2,
                pause_time=Duration.minutes(5),
            ),
        )

        self.app_asg.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            cooldown=Duration.minutes(3),
        )

        # Registrar el ASG en el Target Group
        self.app_asg.attach_to_application_target_group(app_tg)

        # -- Outputs ───────────────────────────────────────────────────────────────
        CfnOutput(self, "AppASGName",
            value=self.app_asg.auto_scaling_group_name,
            export_name="AppASGName",
        )

            