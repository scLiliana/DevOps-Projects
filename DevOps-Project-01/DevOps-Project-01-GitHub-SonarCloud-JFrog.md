# Guía de configuración: GitHub · SonarCloud · JFrog Cloud
### DevOps-Project-01 — Java Login App

> Esta guía cubre todo lo que necesitas crear y configurar en los tres servicios externos **antes** de ejecutar el Maven build.

---

## Índice

1. [GitHub — Fork y configuración del repositorio](#1-github)
2. [SonarCloud — Cuenta, organización, proyecto y token](#2-sonarcloud)
3. [JFrog Cloud — Cuenta, repositorio Maven y token](#3-jfrog-cloud)
4. [Conectar los tres servicios entre sí](#4-conectar-todo)
5. [Verificación final antes del build](#5-verificacion)

---

## 1. GitHub

### 1.1 Hacer Fork del repositorio original

1. Abre https://github.com/NotHarshhaa/DevOps-Projects
2. Haz clic en el botón **Fork** (esquina superior derecha)
3. Selecciona tu cuenta como destino
4. Una vez creado el fork, clónalo localmente:

```bash
git clone https://github.com/TU_USUARIO/DevOps-Projects.git
cd DevOps-Projects/DevOps-Project-01/Java-Login-App
```

---

### 1.2 Crear los Secrets del repositorio

Los secrets guardan de forma segura los tokens de SonarCloud y JFrog para usarlos en GitHub Actions sin exponerlos en el código.

**Ruta:** `Tu repo → Settings → Secrets and variables → Actions → New repository secret`

| Nombre del secret | Valor | De dónde lo obtienes |
|---|---|---|
| `SONAR_TOKEN` | Token de autenticación | Sección 2.4 de esta guía |
| `JFROG_USERNAME` | Tu usuario de JFrog | Tu cuenta JFrog |
| `JFROG_PASSWORD` | Tu Access Token de JFrog | Sección 3.5 de esta guía |

---

### 1.3 Crear el workflow de GitHub Actions (CI/CD)

Crea las carpetas y el archivo:

```bash
mkdir -p .github/workflows
touch .github/workflows/ci.yml
```

Contenido del archivo `.github/workflows/ci.yml`:

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
          fetch-depth: 0  # Necesario para SonarCloud (análisis completo)

      - name: Configurar JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'zulu'
          cache: maven

      - name: Cache de paquetes SonarCloud
        uses: actions/cache@v4
        with:
          path: ~/.sonar/cache
          key: ${{ runner.os }}-sonar
          restore-keys: ${{ runner.os }}-sonar

      - name: Cache de paquetes Maven
        uses: actions/cache@v4
        with:
          path: ~/.m2
          key: ${{ runner.os }}-m2-${{ hashFiles('**/pom.xml') }}
          restore-keys: ${{ runner.os }}-m2

      - name: Build, análisis Sonar y deploy a JFrog
        working-directory: DevOps-Project-01/Java-Login-App
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: https://sonarcloud.io
          JFROG_USERNAME: ${{ secrets.JFROG_USERNAME }}
          JFROG_PASSWORD: ${{ secrets.JFROG_PASSWORD }}
        run: |
          mvn clean verify \
            org.sonarsource.scanner.maven:sonar-maven-plugin:sonar \
            -Dsonar.projectKey=TU_PROYECT_KEY \
            -Dsonar.organization=TU_ORG_KEY \
            -Dsonar.token=$SONAR_TOKEN \
            -s settings.xml
```

Luego haz commit y push:

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add CI workflow with SonarCloud and JFrog"
git push origin master
```

---

## 2. SonarCloud

### 2.1 Crear cuenta

1. Ve a https://sonarcloud.io
2. Haz clic en **Sign up** → elige **Log in with GitHub**
3. Autoriza a SonarCloud el acceso a tu cuenta de GitHub

---

### 2.2 Crear una organización en SonarCloud

1. En el dashboard, haz clic en **"+"** → **"Analyze new project"**
2. Selecciona **"Import an organization from GitHub"**
3. Elige tu cuenta u organización de GitHub
4. Haz clic en **"Install"** para dar permisos a SonarCloud

> ⚠️ Guarda el **Organization Key** que aparece en la URL. Lo necesitarás en el `pom.xml` y en el `ci.yml`.

---

### 2.3 Crear el proyecto en SonarCloud

1. Desde tu organización, haz clic en **"Set up new project"**
2. Busca tu repositorio `DevOps-Projects` y selecciónalo
3. Elige **"Set up"**
4. En la pantalla de configuración, selecciona **Analysis Method: With GitHub Actions**
5. Anota el **Project Key** que aparece

> 💡 Puedes encontrar ambas claves en: `Tu proyecto → Information` (ícono ℹ️ en la barra lateral)

> ⚠️ **Importante:** SonarCloud activa el **Automatic Analysis** por defecto al conectar GitHub. Esto entra en conflicto con el análisis manual de Maven y causa este error:
> ```
> You are running manual analysis while Automatic Analysis is enabled.
> ```
> Para solucionarlo:
> 1. Ve a tu proyecto en SonarCloud
> 2. **Administration → Analysis Method**
> 3. Desactiva el toggle **"Automatic Analysis"**
> 4. Haz clic en **Save**

---

### 2.4 Generar el token de autenticación

1. Haz clic en tu avatar → **"My Account"**
2. Ve a la pestaña **"Security"**
3. Escribe un nombre (ej: `devops-project-01`) y haz clic en **"Generate"**
4. **Copia el token inmediatamente** — no se muestra de nuevo

```
Token generado: sqp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

5. Guárdalo como secret en GitHub con el nombre `SONAR_TOKEN`

---

### 2.5 Configurar el `pom.xml`

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

---

### 2.6 Ejecutar el análisis manualmente (desde la EC2 o local)

```bash
export SONAR_TOKEN=sqp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

cd DevOps-Project-01/Java-Login-App
mvn clean verify \
    org.sonarsource.scanner.maven:sonar-maven-plugin:sonar \
    -Dsonar.projectKey=TU_PROYECT_KEY \
    -Dsonar.organization=TU_ORG_KEY \
    -Dsonar.host.url=https://sonarcloud.io \
    -Dsonar.token=$SONAR_TOKEN \
    -s settings.xml
```

Los resultados aparecen en: `https://sonarcloud.io/dashboard?id=TU_PROYECT_KEY`

---

## 3. JFrog Cloud

### 3.1 Crear cuenta

1. Ve a https://jfrog.com/start-free/
2. Elige la opción **"JFrog Free Forever"**
3. Elige un nombre para tu instancia — define tu URL:
   ```
   https://TU_INSTANCIA.jfrog.io
   ```
4. Selecciona la región más cercana (us-east-1 para coincidir con AWS)

---

### 3.2 Crear el repositorio local Maven

1. **Administration → Repositories → Add Repositories → Local Repository**
2. Selecciona tipo de paquete: **Maven**

| Campo | Valor |
|---|---|
| Repository Key | `libs-release-local` |
| Handle Releases | activado |
| Handle Snapshots | desactivado |

---

### 3.3 Crear repositorio remoto (proxy de Maven Central)

Este repositorio es **indispensable**. Sin él Maven descarga dependencias de Spring, MySQL, etc. desde JFrog y recibe una página HTML en lugar del `.pom`, rompiendo el build con este error:
```
Non-parseable POM: Expected root element 'project' but found 'html'
```

1. **Add Repositories → Remote Repository → Maven**

| Campo | Valor |
|---|---|
| Repository Key | `maven-central-remote` |
| URL | `https://repo1.maven.org/maven2` |

---

### 3.4 Crear repositorio virtual (agrupa local + remoto)

El repositorio virtual es el punto único de entrada para Maven:

1. **Add Repositories → Virtual Repository → Maven**

| Campo | Valor |
|---|---|
| Repository Key | `maven-virtual` |
| Default Deployment Repo | `libs-release-local` |

2. Agrega a "Selected Repositories": `libs-release-local` + `maven-central-remote`

```
maven-virtual  (punto único de entrada)
    ├── libs-release-local    <- tus artefactos (.war)
    └── maven-central-remote  <- proxy a repo1.maven.org
```

---

### 3.5 Generar Access Token de JFrog

1. Haz clic en tu avatar → **"Edit Profile"**
2. **Authentication Settings** → ícono de llave → genera tu **API Key**
3. O desde: **Administration → Identity and Access → Access Tokens → Generate Token**

```
Token: cmVmdGtuOjAxO...
```

4. Guárdalo como secrets en GitHub:
   - `JFROG_USERNAME` → tu email de JFrog
   - `JFROG_PASSWORD` → el Access Token

---

### 3.6 Configurar `settings.xml` para Maven

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

> ⚠️ **Nunca** subas este archivo con credenciales reales. Agrégalo al `.gitignore`:
> ```bash
> echo "settings.xml" >> .gitignore
> ```

---

### 3.7 Configurar `pom.xml` para el deploy a JFrog

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

---

### 3.8 Hacer deploy del artefacto (.war) a JFrog

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

# El .war en JFrog se llama: dptweb-1.0.war (no login-1.0.war)
# Ruta: libs-release-local/com/devopsrealtime/dptweb/1.0/dptweb-1.0.war
```

---

## 4. Conectar todo

### 4.1 Flujo completo de la integración

```
GitHub (código fuente)
        |
        |  git push / PR
        v
GitHub Actions (ci.yml)
        |
        |--- mvn verify -----------------> SonarCloud
        |         └── análisis de calidad      └── Quality Gate
        |                                           └── pasa / falla
        |
        └--- mvn deploy -----------------> JFrog Artifactory
                  └── sube el .war              └── libs-release-local/
                                                     └── dptweb-1.0.war
                                                              |
                                                              v
                                                   EC2 Tomcat (User Data)
                                                   descarga el .war y lo despliega
```

### 4.2 Resumen de los valores que necesitas

| Variable | Dónde la obtienes | Dónde se usa |
|---|---|---|
| `SONAR_TOKEN` | SonarCloud → My Account → Security | GitHub Secret, mvn command |
| `SONAR_PROJECT_KEY` | SonarCloud → Tu proyecto → Information | `pom.xml`, `ci.yml` |
| `SONAR_ORG_KEY` | SonarCloud → Tu organización → URL | `pom.xml`, `ci.yml` |
| `JFROG_INSTANCE` | JFrog → URL de tu instancia | `pom.xml`, `settings.xml` |
| `JFROG_USERNAME` | Tu email de JFrog | `settings.xml`, GitHub Secret |
| `JFROG_ACCESS_TOKEN` | JFrog → Edit Profile → API Key | `settings.xml`, GitHub Secret |
| `WAR_URL` | JFrog → libs-release-local → dptweb-1.0.war → Copy URL | User Data de EC2 Tomcat |

---

## 5. Verificación final

### GitHub
```bash
git remote -v
# Debe apuntar a tu fork, no al repo original
```

### SonarCloud
```bash
curl -u TU_SONAR_TOKEN: \
    https://sonarcloud.io/api/authentication/validate
# Respuesta esperada: {"valid":true}
```

### JFrog
```bash
curl -L -u TU_USUARIO:TU_ACCESS_TOKEN \
    https://TU_INSTANCIA.jfrog.io/artifactory/api/system/ping
# Respuesta esperada: OK
```

### Build completo de prueba
```bash
export SONAR_TOKEN=sqp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

cd DevOps-Project-01/Java-Login-App
mvn clean deploy \
    org.sonarsource.scanner.maven:sonar-maven-plugin:sonar \
    -Dsonar.token=$SONAR_TOKEN \
    -s settings.xml \
    -DskipTests
```

Si todo está correcto verás en la consola:
```
[INFO] ANALYSIS SUCCESSFUL, you can find the results at:
[INFO]   https://sonarcloud.io/dashboard?id=TU_PROYECT_KEY
...
[INFO] Uploading to jfrog-releases: https://TU_INSTANCIA.jfrog.io/.../dptweb-1.0.war
[INFO] BUILD SUCCESS
```

---

*Esta guía es complementaria a `DevOps-Project-01-Guia-Despliegue.md`.*
*Una vez que el `.war` esté en JFrog, las instancias EC2 Tomcat lo descargan automáticamente via el script de User Data al arrancar.*
