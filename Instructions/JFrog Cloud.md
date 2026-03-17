# JFrog Cloud

[[CI/CD]] [[1.DevOps-Proyect-01]] 

## Crear cuenta

1. Ve a [https://jfrog.com/start-free/](https://jfrog.com/start-free/)
2. Elige la opción **"JFrog Free Forever"**
3. Elige un nombre para tu instancia — define tu URL:

```
   https://TU_INSTANCIA.jfrog.io
```

4. Selecciona la región más cercana (us-east-1 para coincidir con AWS)

---

## Crear el repositorio local Maven

1. **Administration → Repositories → Add Repositories → Local Repository**
2. Selecciona tipo de paquete: **Maven**

|Campo|Valor|
|---|---|
|Repository Key|`libs-release-local`|
|Handle Releases|activado|
|Handle Snapshots|desactivado|

---

## Crear repositorio remoto (proxy de Maven Central)

Este repositorio es **indispensable**. Sin él Maven descarga dependencias de Spring, MySQL, etc. desde JFrog y recibe una página HTML en lugar del `.pom`, rompiendo el build con este error:

```
Non-parseable POM: Expected root element 'project' but found 'html'
```

1. **Add Repositories → Remote Repository → Maven**

|Campo|Valor|
|---|---|
|Repository Key|`maven-central-remote`|
|URL|`https://repo1.maven.org/maven2`|
## Crear repositorio virtual (agrupa local + remoto)

El repositorio virtual es el punto único de entrada para Maven:

1. **Add Repositories → Virtual Repository → Maven**

|Campo|Valor|
|---|---|
|Repository Key|`maven-virtual`|
|Default Deployment Repo|`libs-release-local`|

2. Agrega a "Selected Repositories": `libs-release-local` + `maven-central-remote`

```
maven-virtual  (punto único de entrada)
    ├── libs-release-local    <- tus artefactos (.war)
    └── maven-central-remote  <- proxy a repo1.maven.org
```

## Generar Access Token de JFrog

1. Haz clic en tu avatar → **"Edit Profile"**
2. **Authentication Settings** → ícono de llave → genera tu **API Key**
3. O desde: **Administration → Identity and Access → Access Tokens → Generate Token**

```
Token: cmVmdGtuOjAxO...
```

4. Guárdalo como secrets en GitHub:
    - `JFROG_USERNAME` → tu email de JFrog
    - `JFROG_PASSWORD` → el Access Token