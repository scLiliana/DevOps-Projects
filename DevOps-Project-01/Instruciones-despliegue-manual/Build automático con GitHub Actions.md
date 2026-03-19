[[GitHub]] [[1.DevOps-Proyect-01]] [[Infra DevOps]]

**Pre-requisitos:** [[Crear los Secrets del repositorio]] 

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


Crea las carpetas y el archivo:

```bash
mkdir -p .github/workflows
touch .github/workflows/ci.yml
```

El `ci.yml` genera el `settings.xml` desde GitHub Secrets y corre el build automáticamente en cada push:

```yaml
# .github/workflows/ci.yml
name: CI - Build, Analyze & Publish

on:
  push:
    branches: [ main, master ]
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  build-and-analyze:
    name: Build, SonarCloud & Deploy to JFrog
    runs-on: ubuntu-latest

    steps:
      - name: Checkout código
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Configurar JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'zulu'
          cache: maven

      - name: Cache SonarCloud
        uses: actions/cache@v4
        with:
          path: ~/.sonar/cache
          key: ${{ runner.os }}-sonar
          restore-keys: ${{ runner.os }}-sonar

      - name: Cache Maven
        uses: actions/cache@v4
        with:
          path: ~/.m2
          key: ${{ runner.os }}-m2-${{ hashFiles('**/pom.xml') }}
          restore-keys: ${{ runner.os }}-m2

      - name: Generar settings.xml desde GitHub Secrets
        working-directory: DevOps-Project-01/Java-Login-App
        run: |
          cat > settings.xml << EOF
          <?xml version="1.0" encoding="UTF-8"?>
          <settings>
              <servers>
                  <server>
                      <id>jfrog-releases</id>
                      <username>${{ secrets.JFROG_USERNAME }}</username>
                      <password>${{ secrets.JFROG_PASSWORD }}</password>
                  </server>
                  <server>
                      <id>jfrog-virtual</id>
                      <username>${{ secrets.JFROG_USERNAME }}</username>
                      <password>${{ secrets.JFROG_PASSWORD }}</password>
                  </server>
              </servers>
              <profiles>
                  <profile>
                      <id>jfrog</id>
                      <repositories>
                          <repository>
                              <id>jfrog-virtual</id>
                              <url>https://devopsproyect01.jfrog.io/artifactory/maven-virtual</url>
                              <releases><enabled>true</enabled></releases>
                              <snapshots><enabled>false</enabled></snapshots>
                          </repository>
                      </repositories>
                      <pluginRepositories>
                          <pluginRepository>
                              <id>jfrog-virtual</id>
                              <url>https://devopsproyect01.jfrog.io/artifactory/maven-virtual</url>
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
          EOF

      - name: Build, análisis Sonar y deploy a JFrog
        working-directory: DevOps-Project-01/Java-Login-App
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: https://sonarcloud.io
        run: |
          mvn clean deploy \
            org.sonarsource.scanner.maven:sonar-maven-plugin:sonar \
            -Dsonar.projectKey=${{ secrets.SONAR_PROJECT_KEY }} \
            -Dsonar.organization=${{ secrets.SONAR_ORG }} \
            -Dsonar.token=$SONAR_TOKEN \
            -s settings.xml \
            -DskipTests

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


Luego haz commit y push:

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add CI workflow with SonarCloud and JFrog"
git push origin master
```

Verificar que todo salió bien
+ [[12Maven Build#Instancia]]
+ [[12Maven Build#Conectarse a la instancia Maven]]
+ [[12Maven Build#Hacer deploy del artefacto (.war) a JFrog]] 
+ [[12Maven Build#Build completo de prueba]]
