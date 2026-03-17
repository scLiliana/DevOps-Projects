
# SonarCloud

[[CI/CD]] [[1.DevOps-Proyect-01]] 
## Crear cuenta

1. Ve a [https://sonarcloud.io](https://sonarcloud.io)
2. Haz clic en **Sign up** → elige **Log in with GitHub**
3. Autoriza a SonarCloud el acceso a tu cuenta de GitHub

## Crear una organización en SonarCloud

1. En el dashboard, haz clic en **"+"** → **"Analyze new project"**
2. Selecciona **"Import an organization from GitHub"**
3. Elige tu cuenta u organización de GitHub
4. Haz clic en **"Install"** para dar permisos a SonarCloud

> ⚠️ Guarda el **Organization Key** que aparece en la URL. Lo necesitarás en el `pom.xml` y en el `ci.yml`.


## Crear el proyecto en SonarCloud

1. Desde tu organización, haz clic en **"Set up new project"**
2. Busca tu repositorio `DevOps-Projects` y selecciónalo
3. Elige **"Set up"**
4. En la pantalla de configuración, selecciona **Analysis Method: With GitHub Actions**
5. Anota el **Project Key** que aparece

> 💡 Puedes encontrar ambas claves en: `Tu proyecto → Information` (ícono ℹ️ en la barra lateral)

> ⚠️ **Importante:** SonarCloud activa el **Automatic Analysis** por defecto al conectar GitHub. Esto entra en conflicto con el análisis manual de Maven y causa este error:

``` You are running manual analysis while Automatic Analysis is enabled```

 Para solucionarlo:
1. Ve a tu proyecto en SonarCloud
2. **Administration → Analysis Method**
3. Desactiva el toggle **"Automatic Analysis"**
4. Haz clic en **Save**

## Generar el token de autenticación

1. Haz clic en tu avatar → **"My Account"**
2. Ve a la pestaña **"Security"**
3. Escribe un nombre (ej: `devops-project-01`) y haz clic en **"Generate"**
4. **Copia el token inmediatamente** — no se muestra de nuevo

```
Token generado: sqp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

5. Guárdalo como secret en GitHub con el nombre `SONAR_TOKEN`

