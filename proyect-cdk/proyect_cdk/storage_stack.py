"""
StorageStack      → S3 Bucket + CloudWatch Alarms
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
)
from constructs import Construct

class StorageStack(Stack):
    """
    Stack 3 — S3 y CloudWatch
    Crea:
      - S3 Bucket para logs de Tomcat (con versionado y lifecycle)
      - SNS Topic para alertas
      - Alarma CloudWatch para conexiones de BD
    """

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            alert_email: str, 
            **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── S3 Bucket para logs ───────────────────────────────────────────────
        self.bucket = s3.Bucket(
            self, "TomcatLogsBucket",
            bucket_name=f"devops-proyect-01-logs-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,  # Eliminar bucket al destruir stack
            auto_delete_objects=True,  # Eliminar objetos al destruir bucket
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # Bloquear acceso público
            encryption=s3.BucketEncryption.S3_MANAGED,  # Encriptación gestionada por S3
            lifecycle_rules=[
                s3.LifecycleRule(
                    # Mover logs a Infrequent Access después de 30 días
                    id="MoveToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                    ],  
                ),
                s3.LifecycleRule(
                    # Eliminar versiones antiguas despues de 90 días
                    id="DeleteOldVersions",
                    noncurrent_version_expiration=Duration.days(90),
                ),

                # Eliminar logs después de 365 días
                s3.LifecycleRule(
                        id="ExpireLogs",
                        expiration=Duration.days(365),
                    ),
            ],
        )

        # Crear carpetas base dentro del bucket
        # (S3 no tiene carpetas reales — se crean poniendo un objeto vacío)

        
        # ── SNS Topic para alertas ────────────────────────────────────────────
        self.alert_topic = sns.Topic(
            self, "AlertTopic",
            topic_name="DevOpsProyectAlerts",
            display_name="DevOps Proyect-01 Alerts",
        )

        # Suscripción de email al topic
        self.alert_topic.add_subscription(
            sns_subscriptions.EmailSubscription(alert_email)
        )

        # ── Alarma CloudWatch — Conexiones de BD altas ────────────────────────
        db_connections_alarm = cloudwatch.Alarm(
            self, "DBConnectionsHighAlarm",
            alarm_name="DBConnectionsHigh",
            alarm_description="Conexiones a RDS en el umbral de 100",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="DatabaseConnections",
                dimensions_map={
                    "DBInstanceIdentifier": "prod-mysql",  # Reemplazar con el ID real
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=100,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        db_connections_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )

        # ── Alarma CloudWatch — CPU Tomcat alta ───────────────────────────────
        cpu_alarm = cloudwatch.Alarm(
            self, "TomcatCPUHighAlarm",
            alarm_name="TomcatCPUHigh",
            alarm_description="CPU de instancias Tomcat supero el 80%",
            metric=cloudwatch.Metric(
                namespace="AWS/EC2",
                metric_name="CPUUtilization",
                dimensions_map={
                    "AutoScalingGroupName": "tomcat-asg",  # Reemplazar con el nombre real del ASG
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,  # CPU idle < 20% → CPU alta
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        cpu_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )


        # ── Outputs ───────────────────────────────────────────────────────────

        CfnOutput(self, "LogsBucketName", 
            value=self.bucket.bucket_name, 
            description="Nombre del bucket S3 para logs de Tomcat",
            export_name="LogsBucketName"
        )
        CfnOutput(self, "LogsBucketArn", 
            value=self.bucket.bucket_arn,
            description="ARN del bucket S3 para logs",
            export_name="LogsBucketArn"
        )
        CfnOutput(self, "AlertTopicArn", 
            value=self.alert_topic.topic_arn,
            description="ARN del SNS Topic para alertas",
            export_name="AlertTopicArn"
        )
