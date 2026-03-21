from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct

class LaunchTemplateStack(Stack):
    """
    Stack — Launch Template para ASGs
    Crea:
          Launch Template:
                - LaunchTemplate
                    - AMI: Golden AMI
                    - Instance Type: t3.micro
                    - Userdata: pull code from Git + start httpd
                    - IAM Role: AppServerRole
                    - Security Group: SG-AppServers
                    - Key Pair: DevOpsKeyPair
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        appservers_sg: ec2.SecurityGroup,
        global_ami_id: str,
        key_pair_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── IAM Role — importar UNA sola vez y reutilizar en ambos LTs ────────
        app_role = iam.Role.from_role_name(self, "AppServerRole", role_name="AppServerRole")

        # ── User Data — App ────────────────────────────────────────────────
        app_user_data = ec2.UserData.for_linux()
        app_user_data.add_commands(
            "set -euxo pipefail",
            "exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1",
            'echo "=== START: $(date) ==="',

            # ── Variables ────────────────────────────────────────────────────────────
            'GIT_REPO="https://github.com/scLiliana/DevOps-Project-2.git"',
            'GIT_BRANCH="main"',
            'WEB_ROOT="/var/www/html"',
            'APP_SUBDIR="DevOps-Project-02/html-web-app"',
            'CLONE_DIR="/tmp/repo"',

            # ── Actualizar sistema e instalar dependencias ────────────────────────────
            "yum update -y",
            "yum install -y httpd git",

            # ── Habilitar y arrancar Apache ───────────────────────────────────────────
            "systemctl enable httpd",
            "systemctl start httpd",

            # ── Clonar o actualizar el repositorio ────────────────────────────────────
            'if [ -d "${CLONE_DIR}/.git" ]; then',
            '    echo "Repo existe, actualizando..."',
            '    git -C "${CLONE_DIR}" pull origin "${GIT_BRANCH}"',
            "else",
            '    echo "Clonando repositorio..."',
            '    git clone --branch "${GIT_BRANCH}" --depth 1 "${GIT_REPO}" "${CLONE_DIR}"',
            "fi",

            # ── Copiar contenido HTML al document root ────────────────────────────────
            # El /. copia el contenido sin crear subcarpeta extra
            'cp -r "${CLONE_DIR}/${APP_SUBDIR}/." "${WEB_ROOT}/"',

            # ── Permisos ──────────────────────────────────────────────────────────────
            'chown -R apache:apache "${WEB_ROOT}"',
            'chmod -R 755 "${WEB_ROOT}"',

            # ── Configuración desde S3 ────────────────────────────────────────────────
            'ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)',
            'aws s3 cp s3://app-config-bucket-${ACCOUNT_ID}/app.conf /etc/httpd/conf.d/app.conf || echo "WARNING: No se encontró app.conf en S3, usando config por defecto"',

            # ── Recargar Apache con la nueva config ───────────────────────────────────
            "systemctl reload httpd",

            # ── Verificación final ────────────────────────────────────────────────────
            'echo "Verificando Apache..."',
            "systemctl status httpd --no-pager",
            'echo "Verificando contenido..."',
            'ls -la "${WEB_ROOT}"',

            'echo "=== END: $(date) ==="',
        )
        
        # ── Launch Template — App ─────────────────────────────────────────────
        self.launch_template_app = ec2.LaunchTemplate(  
            self, "AppLT",
            launch_template_name="AppLT",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            machine_image=ec2.MachineImage.generic_linux(
                ami_map={"us-east-1": global_ami_id}
            ),
            security_group=appservers_sg,
            user_data=app_user_data,
            role=app_role,
            key_pair=ec2.KeyPair.from_key_pair_name(
                self, "DevOpsKeyPair",
                key_pair_name=key_pair_name,
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

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(
            self, "AppLaunchTemplateId",
            value=self.launch_template_app.launch_template_id,  
            description="ID del Launch Template para ASG de la aplicación",
        )

