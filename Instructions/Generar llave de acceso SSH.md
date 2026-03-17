
Un par de claves (Key Pair) es un conjunto de credenciales criptográficas, compuesto por una clave pública (cifrado/cierre) y una clave privada (descifrado/apertura), utilizadas principalmente para la autenticación segura en servidores, como las instancias de Amazon EC2, permitiendo el acceso sin contraseñas.
## Generar una Key Pair 


```bash
# Generación de la llave con nombre DevOpsKeyPair

aws ec2 create-key-pair \
    --key-name DevOpsKeyPair \
    --query "KeyMaterial" \
    --output text > ~/.ssh/DevOpsKeyPair.pem
    

# Configuración de permisos del archivo

chmod 400 ~/.ssh/DevOpsKeyPair.pem

```
