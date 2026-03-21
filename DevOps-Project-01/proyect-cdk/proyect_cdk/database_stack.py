from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
    SecretValue,
    aws_ec2 as ec2,
    aws_rds as rds,
)
from constructs import Construct


class DatabaseStack(Stack):
    """
    Stack 4 — RDS MySQL Multi-AZ
    Crea:
      - DB Subnet Group (subnets aisladas AZ-1a y AZ-1b)
      - RDS MySQL 8.0 Multi-AZ
      - Parameter Group con configuraciones optimizadas
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        database_sg: ec2.SecurityGroup,
        db_password: str,   # Contraseña del usuario admin
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── DB Subnet Group ───────────────────────────────────────────────────
        # Usa las subnets aisladas (sin acceso a internet)
        subnet_group = rds.SubnetGroup(
            self, "DBSubnetGroup",
            subnet_group_name="mydbsubnetgroup",
            description="Subnet group para RDS MySQL Multi-AZ",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
        )

        # ── Parameter Group — configuraciones MySQL ───────────────────────────
        param_group = rds.ParameterGroup(
            self, "MySQLParamGroup",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            description="Parameter group para MySQL 8.0",
            parameters={
                "character_set_server": "utf8mb4",
                "character_set_client": "utf8mb4",
                "collation_server": "utf8mb4_unicode_ci",
                "max_connections": "200",
                "slow_query_log": "1",
                "long_query_time": "2",
            },
        )

        # ── RDS MySQL Multi-AZ ────────────────────────────────────────────────
        self.db_instance = rds.DatabaseInstance(
            self, "ProdMySQL",
            instance_identifier="prod-mysql",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            subnet_group=subnet_group,
            security_groups=[database_sg],
            credentials=rds.Credentials.from_password(
                username="admin",
                password=SecretValue.unsafe_plain_text(db_password),
            ),
            database_name="UserDB",             # crea la BD automáticamente
            multi_az=True,                      # Multi-AZ para alta disponibilidad
            allocated_storage=20,               # GB
            max_allocated_storage=100,          # autoscaling de almacenamiento
            storage_encrypted=True,
            backup_retention=Duration.days(1),
            deletion_protection=False,          # cambiar a True en producción real
            removal_policy=RemovalPolicy.DESTROY,
            parameter_group=param_group,
            publicly_accessible=False,
            cloudwatch_logs_exports=["error", "slowquery"],
            enable_performance_insights=False,
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "RDSEndpoint",
            value=self.db_instance.db_instance_endpoint_address,
            description="Endpoint del RDS MySQL",
            export_name="RDSEndpoint",
        )
        CfnOutput(self, "RDSPort",
            value=self.db_instance.db_instance_endpoint_port,
            description="Puerto del RDS MySQL",
            export_name="RDSPort",
        )
        CfnOutput(self, "RDSDatabaseName",
            value="UserDB",
            description="Nombre de la base de datos",
            export_name="RDSDatabaseName",
        )
        CfnOutput(self, "RDSJdbcUrl",
            value=f"jdbc:mysql://{self.db_instance.db_instance_endpoint_address}:3306/UserDB",
            description="JDBC URL para application.properties",
            export_name="RDSJdbcUrl",
        )