# Crear los Secrets del repositorio

[[GitHub]]

**Pre-requisitos:** [[SonarCloud]] [[JFrog Cloud]]

Los secrets guardan de forma segura los tokens de SonarCloud y JFrog para usarlos en GitHub Actions sin exponerlos en el código.

**Ruta:** `Tu repo → Settings → Secrets and variables → Actions → New repository secret`

| Nombre del secret   | Valor                    |
| ------------------- | ------------------------ |
| `SONAR_TOKEN`       | Token de autenticación   |
| `SONAR_ORG`         | Id de organización       |
| `SONAR_PROJECT_KEY` | Key del proyecto         |
| `JFROG_USERNAME`    | Tu usuario de JFrog      |
| `JFROG_PASSWORD`    | Tu Access Token de JFrog |
