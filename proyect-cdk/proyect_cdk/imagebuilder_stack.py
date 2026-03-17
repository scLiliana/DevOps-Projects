from aws_cdk import (
    Stack,
    CfnOutput,
    aws_imagebuilder as imagebuilder,
    aws_iam as iam,
    aws_ec2 as ec2,
)
from constructs import Construct


class ImageBuilderStack(Stack):
    """
    Stack 0 — EC2 Image Builder
    Crea pipelines para generar las Golden AMIs:
      - GlobalAMI-Base     → CloudWatch Agent + SSM Agent
      - NginxGoldenAMI     → Base + Nginx
      - TomcatGoldenAMI    → Base + Amazon Corretto 17 + Tomcat 9
      - MavenGoldenAMI     → Base + Amazon Corretto 17 + Maven + Git

    USO:
      1. cdk deploy ImageBuilderStack
      2. En la consola AWS → EC2 Image Builder → Pipelines
      3. Seleccionar cada pipeline → Actions → Run pipeline
      4. Esperar ~15-20 min por pipeline
      5. Anotar los AMI IDs resultantes y ponerlos en app.py
    """

    def __init__(self, scope: "Construct", construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── AMI base de Amazon Linux 2 ────────────────────────────────────────
        # Image Builder usa ARNs de AMIs gestionadas por AWS
        AL2_AMI_ARN = (
            f"arn:aws:imagebuilder:{self.region}:aws:image"
            "/amazon-linux-2-x86/x.x.x"
        )

        # ── IAM Role para Image Builder ───────────────────────────────────────
        ib_role = iam.Role(
            self, "ImageBuilderRole",
            role_name="EC2ImageBuilderRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "EC2InstanceProfileForImageBuilder"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "EC2InstanceProfileForImageBuilderECRContainerBuilds"
                ),
            ],
        )

        ib_instance_profile = iam.CfnInstanceProfile(
            self, "ImageBuilderInstanceProfile",
            instance_profile_name="EC2ImageBuilderProfile",
            roles=[ib_role.role_name],
        )

        # ── Infrastructure Configuration (compartida por todos los pipelines) ─
        infra_config = imagebuilder.CfnInfrastructureConfiguration(
            self, "IBInfraConfig",
            name="DevOpsProject01-InfraConfig",
            instance_types=["t3.micro"],
            instance_profile_name=ib_instance_profile.instance_profile_name,
            terminate_instance_on_failure=True,
        )
        infra_config.add_dependency(ib_instance_profile)

        # ═══════════════════════════════════════════════════════════════════════
        # COMPONENTES — scripts que se ejecutan para instalar el software
        # ═══════════════════════════════════════════════════════════════════════

        # ── Componente 1: Agentes base (CloudWatch + SSM) ─────────────────────
        base_component = imagebuilder.CfnComponent(
            self, "BaseAgentsComponent",
            name="DevOpsProject01-BaseAgents",
            version="1.0.0",
            platform="Linux",
            data="""
name: InstallBaseAgents
description: Instala CloudWatch Agent y SSM Agent
schemaVersion: 1.0

phases:
  - name: build
    steps:
      - name: InstallCloudWatchAgent
        action: ExecuteBash
        inputs:
          commands:
            - sudo yum install -y amazon-cloudwatch-agent
            - sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a start
            - sudo systemctl enable amazon-cloudwatch-agent

      - name: InstallSSMAgent
        action: ExecuteBash
        inputs:
          commands:
            - sudo yum install -y amazon-ssm-agent
            - sudo systemctl enable amazon-ssm-agent
            - sudo systemctl start amazon-ssm-agent

      - name: VerifyAgents
        action: ExecuteBash
        inputs:
          commands:
            - sudo systemctl status amazon-ssm-agent --no-pager
            - echo "Agentes base instalados correctamente"

  - name: validate
    steps:
      - name: ValidateSSM
        action: ExecuteBash
        inputs:
          commands:
            - systemctl is-active amazon-ssm-agent || exit 1
            - echo "Validacion OK"
""",
        )

        # ── Componente 2: Nginx ───────────────────────────────────────────────
        nginx_component = imagebuilder.CfnComponent(
            self, "NginxComponent",
            name="DevOpsProject01-Nginx",
            version="1.0.0",
            platform="Linux",
            data="""
name: InstallNginx
description: Instala Nginx y script de metricas de memoria
schemaVersion: 1.0

phases:
  - name: build
    steps:
      - name: InstallNginx
        action: ExecuteBash
        inputs:
          commands:
            - sudo amazon-linux-extras install nginx1 -y
            - sudo systemctl start nginx
            - sudo systemctl enable nginx

      - name: InstallMemoryMetricsScript
        action: ExecuteBash
        inputs:
          commands:
            - |
              sudo tee /usr/local/bin/memory-metrics.sh << 'SCRIPT'
              #!/bin/bash
              while true; do
                INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
                MEM_USAGE=$(free | grep Mem | awk '{print $3/$2 * 100.0}')
                aws cloudwatch put-metric-data \\
                  --metric-name MemoryUsage \\
                  --namespace Custom \\
                  --value $MEM_USAGE \\
                  --dimensions InstanceId=$INSTANCE_ID
                sleep 60
              done
              SCRIPT
            - sudo chmod +x /usr/local/bin/memory-metrics.sh

      - name: VerifyNginx
        action: ExecuteBash
        inputs:
          commands:
            - nginx -v
            - echo "Nginx instalado correctamente"

  - name: validate
    steps:
      - name: ValidateNginx
        action: ExecuteBash
        inputs:
          commands:
            - systemctl is-active nginx || exit 1
            - echo "Nginx validado OK"
""",
        )

        # ── Componente 3: Amazon Corretto 17 + Tomcat 9 ───────────────────────
        tomcat_component = imagebuilder.CfnComponent(
            self, "TomcatComponent",
            name="DevOpsProject01-Tomcat",
            version="1.0.0",
            platform="Linux",
            data="""
name: InstallTomcat
description: Instala Amazon Corretto 17 y Apache Tomcat 9
schemaVersion: 1.0

phases:
  - name: build
    steps:
      - name: InstallCorretto17
        action: ExecuteBash
        inputs:
          commands:
            - sudo amazon-linux-extras enable corretto17
            - sudo yum install -y java-17-amazon-corretto-devel
            - java -version

      - name: InstallTomcat
        action: ExecuteBash
        inputs:
          commands:
            - TOMCAT_VERSION="9.0.115"
            - wget -q https://dlcdn.apache.org/tomcat/tomcat-9/v${TOMCAT_VERSION}/bin/apache-tomcat-${TOMCAT_VERSION}.tar.gz
            - sudo tar -xzf apache-tomcat-${TOMCAT_VERSION}.tar.gz -C /opt/
            - sudo ln -s /opt/apache-tomcat-${TOMCAT_VERSION} /opt/tomcat
            - sudo useradd -r -m -U -d /opt/tomcat -s /bin/false tomcat
            - sudo chown -R tomcat:tomcat /opt/tomcat
            - rm apache-tomcat-${TOMCAT_VERSION}.tar.gz

      - name: CreateTomcatService
        action: ExecuteBash
        inputs:
          commands:
            - |
              sudo tee /etc/systemd/system/tomcat.service << 'SERVICE'
              [Unit]
              Description=Apache Tomcat 9
              After=network.target

              [Service]
              Type=forking
              Environment=JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto
              Environment=CATALINA_PID=/opt/tomcat/temp/tomcat.pid
              Environment=CATALINA_HOME=/opt/tomcat
              Environment=CATALINA_BASE=/opt/tomcat
              Environment='CATALINA_OPTS=-Xms512M -Xmx1024M -server -XX:+UseParallelGC'
              Environment='JAVA_OPTS=-Djava.awt.headless=true -Djava.security.egd=file:/dev/./urandom'
              ExecStart=/opt/tomcat/bin/startup.sh
              ExecStop=/opt/tomcat/bin/shutdown.sh
              User=tomcat
              Group=tomcat
              UMask=0007
              RestartSec=10
              Restart=always

              [Install]
              WantedBy=multi-user.target
              SERVICE
            - sudo systemctl daemon-reload
            - sudo systemctl enable tomcat
            - sudo systemctl start tomcat

      - name: VerifyTomcat
        action: ExecuteBash
        inputs:
          commands:
            - sleep 10
            - curl -s http://localhost:8080/ | grep -i "tomcat" && echo "Tomcat OK" || exit 1

  - name: validate
    steps:
      - name: ValidateTomcat
        action: ExecuteBash
        inputs:
          commands:
            - systemctl is-active tomcat || exit 1
            - echo "Tomcat validado OK"
""",
        )

        # ── Componente 4: Amazon Corretto 17 + Maven + Git ────────────────────
        maven_component = imagebuilder.CfnComponent(
            self, "MavenComponent",
            name="DevOpsProject01-Maven",
            version="1.0.0",
            platform="Linux",
            data="""
name: InstallMaven
description: Instala Git, Amazon Corretto 17 y Apache Maven
schemaVersion: 1.0

phases:
  - name: build
    steps:
      - name: InstallGitAndCorretto
        action: ExecuteBash
        inputs:
          commands:
            - sudo yum install -y git
            - sudo amazon-linux-extras enable corretto17
            - sudo yum install -y java-17-amazon-corretto-devel
            - git --version
            - java -version

      - name: InstallMaven
        action: ExecuteBash
        inputs:
          commands:
            - MAVEN_VERSION="3.8.8"
            - wget -q https://mirrors.ocf.berkeley.edu/apache/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz
            - sudo tar -xzf apache-maven-${MAVEN_VERSION}-bin.tar.gz -C /opt/
            - sudo ln -s /opt/apache-maven-${MAVEN_VERSION} /opt/maven
            - echo "export M2_HOME=/opt/maven" | sudo tee /etc/profile.d/maven.sh
            - echo "export PATH=\\$M2_HOME/bin:\\$PATH" | sudo tee -a /etc/profile.d/maven.sh
            - source /etc/profile.d/maven.sh
            - rm apache-maven-${MAVEN_VERSION}-bin.tar.gz
            - /opt/maven/bin/mvn -version

  - name: validate
    steps:
      - name: ValidateMaven
        action: ExecuteBash
        inputs:
          commands:
            - /opt/maven/bin/mvn -version || exit 1
            - git --version || exit 1
            - echo "Maven y Git validados OK"
""",
        )

        # ═══════════════════════════════════════════════════════════════════════
        # RECIPES — combinan la AMI base con los componentes
        # ═══════════════════════════════════════════════════════════════════════

        # ── Recipe: GlobalAMI-Base ────────────────────────────────────────────
        base_recipe = imagebuilder.CfnImageRecipe(
            self, "BaseRecipe",
            name="DevOpsProject01-Base-Recipe",
            version="1.0.0",
            parent_image=AL2_AMI_ARN,
            components=[
                {"componentArn": base_component.attr_arn},
            ],
            block_device_mappings=[{
                "deviceName": "/dev/xvda",
                "ebs": {
                    "volumeSize": 20,
                    "volumeType": "gp3",
                    "deleteOnTermination": True,
                },
            }],
        )

        # ── Recipe: NginxGoldenAMI ────────────────────────────────────────────
        nginx_recipe = imagebuilder.CfnImageRecipe(
            self, "NginxRecipe",
            name="DevOpsProject01-Nginx-Recipe",
            version="1.0.0",
            parent_image=AL2_AMI_ARN,
            components=[
                {"componentArn": base_component.attr_arn},
                {"componentArn": nginx_component.attr_arn},
            ],
            block_device_mappings=[{
                "deviceName": "/dev/xvda",
                "ebs": {
                    "volumeSize": 20,
                    "volumeType": "gp3",
                    "deleteOnTermination": True,
                },
            }],
        )

        # ── Recipe: TomcatGoldenAMI ───────────────────────────────────────────
        tomcat_recipe = imagebuilder.CfnImageRecipe(
            self, "TomcatRecipe",
            name="DevOpsProject01-Tomcat-Recipe",
            version="1.0.0",
            parent_image=AL2_AMI_ARN,
            components=[
                {"componentArn": base_component.attr_arn},
                {"componentArn": tomcat_component.attr_arn},
            ],
            block_device_mappings=[{
                "deviceName": "/dev/xvda",
                "ebs": {
                    "volumeSize": 20,
                    "volumeType": "gp3",
                    "deleteOnTermination": True,
                },
            }],
        )

        # ── Recipe: MavenGoldenAMI ────────────────────────────────────────────
        maven_recipe = imagebuilder.CfnImageRecipe(
            self, "MavenRecipe",
            name="DevOpsProject01-Maven-Recipe",
            version="1.0.0",
            parent_image=AL2_AMI_ARN,
            components=[
                {"componentArn": base_component.attr_arn},
                {"componentArn": maven_component.attr_arn},
            ],
            block_device_mappings=[{
                "deviceName": "/dev/xvda",
                "ebs": {
                    "volumeSize": 20,
                    "volumeType": "gp3",
                    "deleteOnTermination": True,
                },
            }],
        )

        # ═══════════════════════════════════════════════════════════════════════
        # DISTRIBUTION CONFIGS — nombre que tendrá cada AMI resultante
        # ═══════════════════════════════════════════════════════════════════════

        def make_dist_config(name: str, ami_name: str) -> imagebuilder.CfnDistributionConfiguration:
            return imagebuilder.CfnDistributionConfiguration(
                self, name,
                name=f"DevOpsProject01-{ami_name}-Dist",
                distributions=[{
                    "region": self.region,
                    "amiDistributionConfiguration": {
                        "name": f"{ami_name}-{{{{ imagebuilder:buildDate }}}}",
                        "description": f"Golden AMI para {ami_name}",
                        "amiTags": {
                            "Name": ami_name,
                            "Project": "DevOps-Project-01",
                            "ManagedBy": "EC2ImageBuilder",
                        },
                    },
                }],
            )

        base_dist  = make_dist_config("BaseDist",   "GlobalAMI-Base")
        nginx_dist = make_dist_config("NginxDist",  "NginxGoldenAMI")
        tomcat_dist= make_dist_config("TomcatDist", "TomcatGoldenAMI")
        maven_dist = make_dist_config("MavenDist",  "MavenGoldenAMI")

        # ═══════════════════════════════════════════════════════════════════════
        # PIPELINES — unen Recipe + InfraConfig + DistributionConfig
        # ═══════════════════════════════════════════════════════════════════════

        def make_pipeline(
            name: str,
            recipe: imagebuilder.CfnImageRecipe,
            dist: imagebuilder.CfnDistributionConfiguration,
        ) -> imagebuilder.CfnImagePipeline:
            pipeline = imagebuilder.CfnImagePipeline(
                self, f"{name}Pipeline",
                name=f"DevOpsProject01-{name}-Pipeline",
                image_recipe_arn=recipe.attr_arn,
                infrastructure_configuration_arn=infra_config.attr_arn,
                distribution_configuration_arn=dist.attr_arn,
                status="ENABLED",
                # Sin schedule — se ejecuta manualmente desde la consola
                # Para ejecución automática agregar:
                # schedule=imagebuilder.CfnImagePipeline.ScheduleProperty(
                #     schedule_expression="cron(0 0 * * ? *)",
                #     pipeline_execution_start_condition="EXPRESSION_MATCH_ONLY",
                # ),
            )
            pipeline.add_dependency(infra_config)
            return pipeline

        base_pipeline   = make_pipeline("Base",   base_recipe,   base_dist)
        nginx_pipeline  = make_pipeline("Nginx",  nginx_recipe,  nginx_dist)
        tomcat_pipeline = make_pipeline("Tomcat", tomcat_recipe, tomcat_dist)
        maven_pipeline  = make_pipeline("Maven",  maven_recipe,  maven_dist)

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "BasePipelineArn",
            value=base_pipeline.attr_arn,
            description="ARN del pipeline GlobalAMI-Base",
        )
        CfnOutput(self, "NginxPipelineArn",
            value=nginx_pipeline.attr_arn,
            description="ARN del pipeline NginxGoldenAMI",
        )
        CfnOutput(self, "TomcatPipelineArn",
            value=tomcat_pipeline.attr_arn,
            description="ARN del pipeline TomcatGoldenAMI",
        )
        CfnOutput(self, "MavenPipelineArn",
            value=maven_pipeline.attr_arn,
            description="ARN del pipeline MavenGoldenAMI",
        )
        CfnOutput(self, "NextStep",
            value=(
                "1. Ve a EC2 Image Builder → Pipelines "
                "2. Ejecuta cada pipeline en orden: Base → Nginx → Tomcat → Maven "
                "3. Espera ~15-20 min por pipeline "
                "4. Anota los AMI IDs resultantes "
                "5. Ponlos en app.py (tomcat_ami_id y nginx_ami_id)"
            ),
            description="Pasos siguientes después de desplegar este stack",
        )