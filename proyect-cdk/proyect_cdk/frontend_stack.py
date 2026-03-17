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


class FrontendStack(Stack):
    """
    Stack 6 — Frontend: Nginx ASG + NLB público
    Crea:
      - Launch Template para Nginx (configura proxy_pass al NLB interno)
      - Auto Scaling Group (min 1, max 3, desired 2)
      - Target Group TCP:80
      - NLB público (public-nlb) — URL de acceso a la app
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        frontend_sg: ec2.SecurityGroup,
        instance_profile: iam.CfnInstanceProfile,
        nginx_ami_id: str,          # ID de la NginxGoldenAMI
        private_nlb_dns: str,       # DNS del NLB interno (del BackendStack)
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── User Data — configura Nginx como reverse proxy ────────────────────
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "#!/bin/bash",
            "",
            f'NLB_BACKEND_DNS="{private_nlb_dns}"',
            "",
            "# Eliminar configuración anterior si existe",
            "sudo rm -f /etc/nginx/conf.d/app.conf",
            "",
            "# Crear configuración de Nginx como reverse proxy",
            "sudo tee /etc/nginx/conf.d/app.conf << 'EOF'",
            "upstream backend {",
            f"    server {private_nlb_dns}:8080;",
            "}",
            "server {",
            "    listen 80;",
            "    server_name _;",
            "    location / {",
            "        proxy_pass http://backend;",
            '        proxy_set_header Host "backend";',
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_connect_timeout 60s;",
            "        proxy_read_timeout 60s;",
            "    }",
            "}",
            "EOF",
            "",
            "# Eliminar server block default de nginx.conf para evitar conflicto",
            "sudo sed -i '/^    server {/,/^    }/d' /etc/nginx/nginx.conf || true",
            "",
            "# Verificar configuración y recargar",
            "sudo nginx -t && sudo systemctl reload nginx",
            'echo "Nginx configurado como reverse proxy hacia $NLB_BACKEND_DNS"',
        )

        # ── Launch Template ───────────────────────────────────────────────────
        nginx_ami = ec2.MachineImage.generic_linux(
            ami_map={"us-east-1": nginx_ami_id}
        )

        launch_template = ec2.LaunchTemplate(
            self, "NginxLT",
            launch_template_name="NginxLT",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            machine_image=nginx_ami,
            security_group=frontend_sg,
            user_data=user_data,
            role=iam.Role.from_role_name(
                self, "EC2AppRole", "EC2AppRole"
            ),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=20,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        delete_on_termination=True,
                    ),
                )
            ],
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
            default_target_groups=[self.nginx_tg],
        )

        # ── Auto Scaling Group ────────────────────────────────────────────────
        self.nginx_asg = autoscaling.AutoScalingGroup(
            self, "NginxASG",
            auto_scaling_group_name="nginx-asg",
            vpc=vpc,
            launch_template=launch_template,
            min_capacity=1,
            max_capacity=3,
            desired_capacity=2,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            health_check=autoscaling.HealthCheck.elb(
                grace=Duration.minutes(3)
            ),
        )

        # Registrar el ASG en el Target Group
        self.nginx_asg.attach_to_network_target_group(self.nginx_tg)

        # Scaling policy — escalar cuando CPU > 70%
        self.nginx_asg.scale_on_cpu_utilization(
            "NginxCPUScaling",
            target_utilization_percent=70,
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "PublicNLBDns",
            value=self.public_nlb.load_balancer_dns_name,
            description="DNS del NLB público — URL de la aplicación",
            export_name="PublicNLBDns",
        )
        CfnOutput(self, "AppUrl",
            value=f"http://{self.public_nlb.load_balancer_dns_name}/pages/login.jsp",
            description="URL directa a la página de login",
            export_name="AppUrl",
        )
        CfnOutput(self, "NginxTGArn",
            value=self.nginx_tg.target_group_arn,
            description="ARN del Target Group de Nginx",
            export_name="NginxTGArn",
        )