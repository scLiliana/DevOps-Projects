from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct

class LaunchTemplateStack(Stack):
    """
    Stack 4 — Launch Template para ASGs
    Crea:
      - User Data para Tomcat (descarga WAR desde JFrog al arrancar)  
      - Launch Template para Tomcat (BackendStack)
      - User Data para Nginx (descarga configuración desde S3 al arrancar)
      - Launch Template para Nginx (FrontendStack)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        backend_sg: ec2.SecurityGroup,
        frontend_sg: ec2.SecurityGroup,
        instance_profile: iam.CfnInstanceProfile,
        tomcat_ami_id: str,
        nginx_ami_id: str,
        jfrog_user: str,
        jfrog_token: str,
        rds_endpoint: str,
        db_password: str,
        private_nlb_dns: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── IAM Role — importar UNA sola vez y reutilizar en ambos LTs ────────
        app_role = iam.Role.from_role_name(self, "EC2AppRole", "EC2AppRole")

        # ── User Data — Tomcat ────────────────────────────────────────────────
        tomcat_user_data = ec2.UserData.for_linux()
        tomcat_user_data.add_commands(
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
            "sudo dnf install -y mariadb105 2>/dev/null || sudo yum install -y mysql",
            f"mysql -h {rds_endpoint} -u admin -p'{db_password}' -e \"CREATE DATABASE IF NOT EXISTS UserDB; SHOW DATABASES;\"",
            "sudo systemctl restart tomcat",
        )

        # ── Launch Template — Tomcat ──────────────────────────────────────────
        tomcat_ami = ec2.MachineImage.generic_linux(
            ami_map={"us-east-1": tomcat_ami_id}
        )

        self.launch_template_tomcat = ec2.LaunchTemplate(  # <-- self. para exponerlo
            self, "TomcatLT",
            launch_template_name="TomcatLT",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            machine_image=tomcat_ami,
            security_group=backend_sg,
            user_data=tomcat_user_data,
            role=app_role,  # <-- reutiliza la referencia
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

        # ── User Data — Nginx ─────────────────────────────────────────────────
        nginx_user_data = ec2.UserData.for_linux()
        nginx_user_data.add_commands(
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

        # ── Launch Template — Nginx ───────────────────────────────────────────
        nginx_ami = ec2.MachineImage.generic_linux(
            ami_map={"us-east-1": nginx_ami_id}
        )

        self.launch_template_nginx = ec2.LaunchTemplate(  # <-- self. para exponerlo
            self, "NginxLT",
            launch_template_name="NginxLT",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            machine_image=nginx_ami,
            security_group=frontend_sg,
            user_data=nginx_user_data,
            role=app_role,  
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

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(
            self, "TomcatLaunchTemplateId",
            value=self.launch_template_tomcat.launch_template_id,  
            description="ID del Launch Template para ASG de Tomcat",
        )
        CfnOutput(
            self, "NginxLaunchTemplateId",
            value=self.launch_template_nginx.launch_template_id,   
            description="ID del Launch Template para ASG de Nginx",
        )