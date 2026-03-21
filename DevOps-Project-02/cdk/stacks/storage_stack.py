from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class StorageStack(Stack):
    """
    Crea:
        S3:
            - S3 Bucket: app-config-bucket
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)


        # ── S3 Bucket para logs ───────────────────────────────────────────────
        self.bucket = s3.Bucket(
            self, "AppConfigBucket",
            bucket_name=f"app-config-bucket-{self.account}",
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

        # ── Outputs ───────────────────────────────────────────

        CfnOutput(self, "AppConfigBucketName",
            value=self.bucket.bucket_name,
            description="S3 Bucket para configuración de la aplicación",
            export_name="AppConfigBucketName",
        )