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


class BackendStack(Stack):
    """
    Stack 5 — Backend: Tomcat ASG + NLB interno
    Crea:
      - Launch Template para Tomcat (descarga WAR desde JFrog al arrancar)
      - Auto Scaling Group (min 1, max 3, desired 2)
      - Target Group TCP:8080
      - NLB interno (private-nlb)
    """

    def __init__(
            self, 
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            backend_sg: ec2.SecurityGroup,
            instance_profile: iam.CfnInstanceProfile,
            tomcat_ami_id: str,
            jfrog_user: str,
            jfrog_token: str,
            rds_endpoint: str,
            db_password: str,
            **kwargs
        ) -> None:
            super().__init__(scope, construct_id, **kwargs)

            # ── User Data — descarga WAR desde JFrog y corrige application.properties
            user_data = ec2.UserData.for_linux()
            user_data.add_commands(
                "#!/bin/bash",
                "set -e",
                "",
                "# Variables",
                f'JFROG_USER="{jfrog_user}"',
                f'JFROG_TOKEN="{jfrog_token}"',
                'JFROG_URL="https://devopsproyect01.jfrog.io/artifactory/libs-release-local/com/devopsrealtime/dptweb/1.0/dptweb-1.0.war"',
                'WAR_DEST="/opt/tomcat/webapps/ROOT.war"',
                f'RDS_ENDPOINT="{rds_endpoint}"',
                f'DB_PASSWORD="{db_password}"',
                "",
                "# Limpiar deploy anterior",
                "sudo systemctl stop tomcat || true",
                "sudo rm -f $WAR_DEST",
                "sudo rm -rf /opt/tomcat/webapps/ROOT",
                "",
                "# Descargar WAR desde JFrog con autenticación",
                "sudo wget --user=$JFROG_USER --password=$JFROG_TOKEN \\",
                "    -O $WAR_DEST $JFROG_URL",
                "",
                "# Verificar que el WAR es válido (no una página HTML de error)",
                'WAR_SIZE=$(stat -c%s $WAR_DEST 2>/dev/null || echo 0)',
                'if [ "$WAR_SIZE" -lt 1000000 ]; then',
                '    echo "ERROR: WAR demasiado pequeño ($WAR_SIZE bytes) — fallo de autenticación con JFrog"',
                "    exit 1",
                "fi",
                "",
                "# Iniciar Tomcat para que extraiga el WAR",
                "sudo systemctl start tomcat",
                "sleep 15",
                "",
                "# Corregir application.properties con el endpoint real de RDS",
                'APP_PROPS="/opt/tomcat/webapps/ROOT/WEB-INF/classes/application.properties"',
                'if [ -f "$APP_PROPS" ]; then',
                "    sudo tee $APP_PROPS << EOF",
                f"spring.datasource.url = jdbc:mysql://${{RDS_ENDPOINT}}:3306/UserDB",
                "spring.datasource.username = admin",
                "spring.datasource.password = $DB_PASSWORD",
                "spring.datasource.driver-class-name = com.mysql.cj.jdbc.Driver",
                "spring.jpa.hibernate.ddl-auto = update",
                "EOF",
                "    sudo systemctl restart tomcat",
                '    echo "application.properties actualizado con endpoint RDS"',
                "fi",
            )
            
            # ── Launch Template ───────────────────────────────────────────────────

            tomcat_ami = ec2.MachineImage.generic_linux(
                ami_map={
                    "us-east-1": tomcat_ami_id
                    }  
            )
        
            launch_template = ec2.LaunchTemplate(
                self, "TomcatLT",
                launch_template_name="TomcatLT",
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.T3,
                    ec2.InstanceSize.MICRO,
                ),
                machine_image=tomcat_ami,
                security_group=backend_sg,
                user_data=user_data,
                role= iam.Role.from_role_name(
                    self, "EC2AppRole", "EC2AppRole"
                ),
                block_devices=[
                    ec2.BlockDevice(
                        device_name="/dev/xvda",
                        volume=ec2.BlockDeviceVolume.ebs(
                              volume_size=20, 
                              volume_type=ec2.EbsDeviceVolumeType.GP3,
                              delete_on_termination=True  
                        ),
                    )
                ],
            )
            # ── Target Group TCP:8080 ─────────────────────────────────────────────
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
                    default_target_groups=[self.tomcat_tg],
            )

            # ── Auto Scaling Group ───────────────────────────────────────────────
            self.tomcat_asg = autoscaling.AutoScalingGroup(
                self, "TomcatASG",
                auto_scaling_group_name="tomcat-asg",
                vpc=vpc,
                launch_template=launch_template,
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

            # -- Outputs ───────────────────────────────────────────────────────────────
            CfnOutput(self, "PrivateNLBDns",
                value=self.backend_nlb.load_balancer_dns_name,
                description="DNS del NLB interno (backend)",
                export_name="PrivateNLBDns",
            )
            CfnOutput(self, "TomcatTGArn",
                value=self.tomcat_tg.target_group_arn,
                description="ARN del Target Group de Tomcat",
                export_name="TomcatTGArn",
            )