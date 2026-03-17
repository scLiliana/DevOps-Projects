# Maven build

[[1.DevOps-Proyect-01]][[Infra DevOps]][[AWS]]

> ℹ️ El build lo puede correr **GitHub Actions** (recomendado, automático en cada push) o manualmente en la instancia Maven. Si usas GitHub Actions, el `ci.yml` **[[Build automático con GitHub Actions]]** ya hace todo esto automáticamente — puedes saltar la sección Configurar `settings.xml` para Maven .

## GitHub

### Hacer Fork del repositorio original

1. Abre [https://github.com/NotHarshhaa/DevOps-Projects](https://github.com/NotHarshhaa/DevOps-Projects)
2. Haz clic en el botón **Fork** (esquina superior derecha)
3. Selecciona tu cuenta como destino
4. Una vez creado el fork, clónalo localmente:

```bash
git clone https://github.com/TU_USUARIO/DevOps-Projects.git
cd DevOps-Projects/DevOps-Project-01/Java-Login-App
```

## Configurar el `pom.xml`

### SonarCloud

**Pre-requisitos:** [[SonarCloud]]

Agrega en la sección `<properties>`:

```xml
<properties>
    <!-- Java version -->
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>

    <!-- SonarCloud -->
    <sonar.projectKey>TU_PROYECT_KEY</sonar.projectKey>
    <sonar.organization>TU_ORG_KEY</sonar.organization>
    <sonar.host.url>https://sonarcloud.io</sonar.host.url>
    <!-- El token se pasa como variable de entorno SONAR_TOKEN, no aquí -->
</properties>
```

Agrega el plugin en `<build><plugins>`:

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.sonarsource.scanner.maven</groupId>
            <artifactId>sonar-maven-plugin</artifactId>
            <version>4.0.0.4121</version>
        </plugin>
    </plugins>
</build>
```

### JFrog

**Pre-requisitos:** [[JFrog Cloud]]

Agrega `<distributionManagement>` antes de `</project>`:

```xml
<distributionManagement>
    <repository>
        <id>jfrog-releases</id>
        <name>JFrog Releases</name>
        <url>https://TU_INSTANCIA.jfrog.io/artifactory/libs-release-local</url>
    </repository>
    <snapshotRepository>
        <id>jfrog-snapshots</id>
        <name>JFrog Snapshots</name>
        <url>https://TU_INSTANCIA.jfrog.io/artifactory/libs-snapshot-local</url>
    </snapshotRepository>
</distributionManagement>
```

También asegúrate de tener la versión del conector MySQL — sin esto el build falla con `version is missing`:

```xml
<dependency>
    <groupId>mysql</groupId>
    <artifactId>mysql-connector-java</artifactId>
    <version>8.0.33</version>
</dependency>
```



## Configurar `settings.xml` para Maven

**Pre-requisitos:** [[JFrog Cloud]]

`Para evitar subir credenciales a GitHub este se puede editar dentro de la Instancia de Maven`

Guárdalo en la raíz del proyecto como `settings.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0
                              http://maven.apache.org/xsd/settings-1.0.0.xsd">

    <servers>
        <server>
            <id>jfrog-releases</id>
            <username>TU_USUARIO_JFROG</username>
            <password>TU_ACCESS_TOKEN_JFROG</password>
        </server>
        <server>
            <id>jfrog-virtual</id>
            <username>TU_USUARIO_JFROG</username>
            <password>TU_ACCESS_TOKEN_JFROG</password>
        </server>
    </servers>

    <profiles>
        <profile>
            <id>jfrog</id>
            <!-- Repositorios para dependencias -->
            <repositories>
                <repository>
                    <id>jfrog-virtual</id>
                    <name>JFrog Virtual</name>
                    <url>https://TU_INSTANCIA.jfrog.io/artifactory/maven-virtual</url>
                    <releases><enabled>true</enabled></releases>
                    <snapshots><enabled>false</enabled></snapshots>
                </repository>
            </repositories>
            <!-- Repositorios para plugins — evita errores de POMs corruptos -->
            <pluginRepositories>
                <pluginRepository>
                    <id>jfrog-virtual</id>
                    <name>JFrog Virtual Plugins</name>
                    <url>https://TU_INSTANCIA.jfrog.io/artifactory/maven-virtual</url>
                    <releases><enabled>true</enabled></releases>
                    <snapshots><enabled>false</enabled></snapshots>
                </pluginRepository>
            </pluginRepositories>
        </profile>
    </profiles>

    <activeProfiles>
        <activeProfile>jfrog</activeProfile>
    </activeProfiles>

</settings>
```


## Lanzar instancia Maven

### Recuperar variables necesarias 

En caso de usar [[3.Función para guardar el variables en un documento]] solo cargar las varables

```bash
# Recuperar el Id de la Maven AMI

MAVEN_AMI=$(aws ec2 describe-images --owners self \
    --filters "Name=name,Values=MavenGoldenAMI" \
    --query "Images[0].ImageId" --output text --region us-east-1)
    
save_id "MAVEN_AMI" "$MAVEN_AMI"
```

```bash
# Recuperar el ID de la subnet privada de la AZ 1a

SUBNET_PRIVATE_1A_ID=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_PRIMARY_ID" \
              "Name=tag:Name,Values=PrivateSubnet-1a" \
    --query "Subnets[0].SubnetId" --output text --region us-east-1)
    
save_id "MAVEN_AMI" "$MAVEN_AMI"
```

### Instancia

```bash
# Lanzar instancia desde MavenGoldenAMI

INSTANCE_MAVEN=$(aws ec2 run-instances \
    --image-id $MAVEN_AMI \
    --count 1 \
    --instance-type t3.micro \
    --key-name DevOpsKeyPair \
    --security-group-ids $SG_BACKEND_ID \
    --subnet-id $SUBNET_PRIVATE_1A_ID \
    --iam-instance-profile Name=EC2AppProfile \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=MavenBuildServer}]' \
    --query "Instances[0].InstanceId" \
    --output text --region us-east-1)
    
save_id "INSTANCE_MAVEN" "$INSTANCE_MAVEN"
```

```bash
# Esperar a que la instancia este corriendo
 
aws ec2 wait instance-running \
--instance-ids $INSTANCE_MAVEN \
--region us-east-1

echo "Instancia Maven lista"
```

## Conectarse a la instancia Maven


```bash
# Opción A — Conectarse via SSM (no requiere Bastion ni SSH abierto)
aws ssm start-session --target $INSTANCE_MAVEN --region us-east-1
```

```bash
# Opción B — Conectarse via Bastion + SSH

# Primero obtener la IP privada de la instancia Maven
IP_MAVEN=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_MAVEN \
    --query "Reservations[0].Instances[0].PrivateIpAddress" \
    --output text --region us-east-1)

# Obtener la IP pública del Bastion dinámicamente
IP_BASTION=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=BastionHost" \
              "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text --region us-east-1)
echo "Bastion IP: $IP_BASTION"

ssh -i ~/.ssh/DevOpsKeyPair.pem -J ec2-user@$IP_BASTION ec2-user@$IP_MAVEN
```

## Clonar el proyecto

```bash
# Verificar que tiene todo instalado
git --version && java -version && mvn -version

# Si git no está instalado
sudo yum install -y git

# ⚠️ Amazon Linux 2 NO incluye java-17-openjdk en sus repos por defecto
# El paquete correcto es Amazon Corretto 17
sudo amazon-linux-extras enable corretto17
sudo yum install -y java-17-amazon-corretto-devel
java -version

# Si Maven no está instalado
wget https://mirrors.ocf.berkeley.edu/apache/maven/maven-3/3.8.4/binaries/apache-maven-3.8.4-bin.tar.gz
sudo tar -xvzf apache-maven-3.8.4-bin.tar.gz -C /opt/
sudo ln -s /opt/apache-maven-3.8.4 /opt/maven
echo "export M2_HOME=/opt/maven" | sudo tee /etc/profile.d/maven.sh
echo "export PATH=\$M2_HOME/bin:\$PATH" | sudo tee -a /etc/profile.d/maven.sh
source /etc/profile.d/maven.sh

# Clonar el repositorio
git clone https://github.com/TU_USUARIO/DevOps-Projects.git
cd DevOps-Projects/DevOps-Project-01/Java-Login-App

```

## Hacer deploy del artefacto (.war) a JFrog

```bash
# Si hubo errores previos de POMs corruptos, limpiar el caché primero
rm -rf ~/.m2/repository/

# Verificar que el build funciona sin JFrog (diagnóstico)
echo '<settings></settings>' > /tmp/empty-settings.xml
mvn clean package -DskipTests -s /tmp/empty-settings.xml
# Si esto da BUILD SUCCESS, el código está bien y el problema era JFrog

# Deploy completo a JFrog
cd DevOps-Project-01/Java-Login-App
mvn clean deploy -s settings.xml -DskipTests

# Verificar conexión a JFrog antes del deploy
export JFROG_USERNAME="tu_email@ejemplo.com"
export JFROG_ACCESS_TOKEN="cmVmdGtuOjAx..."
curl -L -u $JFROG_USERNAME:$JFROG_ACCESS_TOKEN \
    https://TU_INSTANCIA.jfrog.io/artifactory/api/system/ping
# Respuesta esperada: OK

```

## Build completo de prueba

```bash
export SONAR_TOKEN=sqp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

cd DevOps-Project-01/Java-Login-App
mvn clean deploy \
    org.sonarsource.scanner.maven:sonar-maven-plugin:sonar \
    -Dsonar.token=$SONAR_TOKEN \
    -s settings.xml \
    -DskipTests
```

