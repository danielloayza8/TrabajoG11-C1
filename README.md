# UniFi AP — Wrapper REST API

Wrapper ligero con FastAPI sobre la API REST del controlador UniFi Network local,
enfocado exclusivamente en los puntos de acceso **UAP-AC-LR / U7LR**.

Puede ejecutarse directamente con Python o dentro de un contenedor Docker.

---

## Índice

1. [Requisitos previos](#requisitos-previos)
2. [Crear cuenta de administrador local](#paso-1--crear-una-cuenta-de-administrador-local)
3. [Ejecución con Python](#paso-2--ejecución-directa-con-python)
4. [Ejecución con Docker](#paso-3--ejecución-con-docker)
5. [Variables de entorno](#variables-de-entorno)
6. [Endpoints disponibles](#endpoints-disponibles)
7. [Solución de problemas](#solución-de-problemas)
8. [Referencia de puertos](#referencia-de-puertos-según-tipo-de-instalación)
9. [Notas técnicas](#notas-técnicas)

---

## Requisitos previos

- Python 3.11+ **o** Docker instalado
- UniFi Network Application en ejecución (instalación propia en Linux/Windows)
- Una cuenta de administrador **local** en el controlador (ver Paso 1)

---

## Paso 1 — Crear una cuenta de administrador local (IMPORTANTE — soluciona el problema del MFA)

### ¿Por qué es necesario esto?

Desde julio de 2024, Ubiquiti exige autenticación multifactor (MFA) en todas las
cuentas vinculadas a la nube (cuentas SSO de Ubiquiti). Esto rompe cualquier proceso
de login automatizado, ya que el segundo factor requiere intervención humana y no
puede ser resuelto por un script o servicio.

La solución es crear una cuenta de administrador **estrictamente local**, es decir,
una cuenta que vive únicamente dentro del controlador UniFi y que **no está vinculada
a ninguna cuenta de Ubiquiti**. Este tipo de cuenta no tiene MFA y se autentica
únicamente con usuario y contraseña, lo que permite el acceso programático sin
interrupciones.

### ¿Por qué el campo Email usa `api@local`?

El formulario de creación de administradores en UniFi solicita un campo de **Email**.
Sin embargo, cuando la cuenta es local (sin vínculo a la nube), este campo **no es
verificado ni utilizado para ningún propósito real**: no se envía ningún correo de
confirmación, no se valida el dominio, y no se usa para el login.

Por esta razón se puede colocar cualquier valor que tenga formato de email válido.
Se recomienda usar algo como `api@local` o `servicio@local` por las siguientes razones:

- **Claridad operacional:** deja claro que es una cuenta de servicio, no de una persona real.
- **Convención de red interna:** el sufijo `.local` es el estándar para recursos en redes
  privadas (mDNS/Bonjour), señalando que este recurso no existe fuera de la LAN.
- **Mantenibilidad:** evita confusiones si otro administrador revisa la lista de cuentas
  en el futuro — queda claro que no hay nadie detrás de esa cuenta.
- **Seguridad:** al no apuntar a ningún dominio real, se elimina cualquier riesgo de que
  un correo de recuperación o notificación llegue a un destinatario externo.

> Lo que **sí importa** para el login de la API es el campo **Username** (nombre de
> usuario), que es el valor que debes colocar en `UNIFI_USER` dentro del archivo `.env`.
> El campo Email es completamente irrelevante para la autenticación local.

### Pasos para crear la cuenta

1. Accede a la interfaz web de tu controlador en `https://<tu-ip>:8443`.
2. Ve a **Settings → Admins**.
3. Haz clic en **+** para agregar un nuevo administrador.
4. Completa los campos:
   - **Email**: `api@local` (o cualquier valor con formato email — no se verifica)
   - **Username**: `api_service` (este es el valor que usarás en `UNIFI_USER`)
5. Marca la casilla **"Set Admin Password"** y establece una contraseña segura.
6. **Desmarca "Remote Access"** — este es el paso crítico. Al desactivarlo, la cuenta
   queda como local pura, sin vínculo a la nube de Ubiquiti y sin requisito de MFA.
7. Asigna el rol según lo que necesites:
   - `View Only` — suficiente para todos los endpoints GET (solo lectura).
   - `Site Administrator` — necesario para los endpoints POST (renombrar, reiniciar, LED).
8. Guarda y verifica que puedes iniciar sesión con las nuevas credenciales.

---

## Paso 2 — Ejecución directa con Python

```bash
# 1. Copia los archivos del proyecto en una carpeta
cd unifi_aclr_api

# 2. Crea un entorno virtual de Python
python -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate

# 3. Instala las dependencias
pip install -r requirements.txt

# 4. Crea el archivo de configuración
cp .env.example .env
# Edita .env con tu editor preferido y completa los valores reales

# 5. Inicia el servidor
uvicorn main:app --host 0.0.0.0 --port 6000 --reload
```

La documentación interactiva (Swagger UI) estará disponible en:
**http://localhost:6000/docs**

---

## Paso 3 — Ejecución con Docker

### ¿Por qué usar Docker aquí?

Contenerizar esta API tiene varias ventajas para un despliegue en red local:

- **Aislamiento:** la API corre en un entorno controlado, sin depender del Python
  ni de las bibliotecas instaladas en el sistema host.
- **Portabilidad:** la misma imagen funciona en cualquier máquina que tenga Docker,
  sin importar el sistema operativo o la versión de Python instalada.
- **Reinicio automático:** combinado con `--restart unless-stopped`, el contenedor
  se levanta solo si el sistema se reinicia, comportándose como un servicio del sistema.
- **Seguridad:** el `Dockerfile` usa un usuario sin privilegios (`appuser`) y una
  construcción en dos etapas (multi-stage) que elimina herramientas de compilación
  de la imagen final, reduciendo la superficie de ataque.

### Estructura del Dockerfile

El `Dockerfile` usa una construcción en **dos etapas**:

1. **Etapa `builder`:** instala y compila todas las dependencias de Python en una
   carpeta aislada usando una imagen completa.
2. **Etapa `final`:** parte de una imagen limpia `python:3.11-slim` y copia solo
   las dependencias ya compiladas. El resultado es una imagen más pequeña y segura.

### Construir la imagen

```bash
# Desde la carpeta raíz del proyecto (donde está el Dockerfile)
docker build -t unifi-aclr-api:latest .
```

### Ejecutar el contenedor

Las credenciales **nunca deben estar dentro de la imagen**. Se inyectan en tiempo
de ejecución mediante `--env-file`, lo que mantiene el archivo `.env` fuera del
contenedor y del repositorio.

```bash
docker run -d \
  --name unifi-aclr-api \
  --restart unless-stopped \
  --env-file .env \
  -p 6000:6000 \
  unifi-aclr-api:latest
```

| Opción | Significado |
|--------|-------------|
| `-d` | Ejecuta el contenedor en segundo plano (detached) |
| `--name` | Nombre legible para identificar el contenedor |
| `--restart unless-stopped` | Se reinicia automáticamente salvo que se detenga manualmente |
| `--env-file .env` | Inyecta las variables de entorno desde el archivo `.env` local |
| `-p 6000:6000` | Mapea el puerto 6000 del host al puerto 6000 interno del contenedor |

### Comandos útiles de gestión

```bash
# Ver los logs en tiempo real (muestra la configuración activa al arrancar)
docker logs -f unifi-aclr-api

# Verificar las variables de entorno que recibe el contenedor
docker exec unifi-aclr-api env | grep -E "UNIFI|ACLR"

# Detener el contenedor
docker stop unifi-aclr-api

# Reiniciar el contenedor (necesario tras cambiar el .env)
docker restart unifi-aclr-api

# Reconstruir y redesplegar tras cambios en el código
docker build -t unifi-aclr-api:latest . && \
docker rm -f unifi-aclr-api && \
docker run -d --name unifi-aclr-api --restart unless-stopped \
  --env-file .env -p 6000:6000 unifi-aclr-api:latest
```

> **Importante:** tras modificar el archivo `.env`, el contenedor debe reiniciarse
> para que los nuevos valores surtan efecto (`docker restart unifi-aclr-api`).

---

## Variables de entorno

Estas variables se configuran en el archivo `.env` y se pasan al contenedor con `--env-file`.

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `UNIFI_HOST` | IP o hostname del controlador (sin barra final, **sin puerto**) | `https://192.168.1.10` |
| `UNIFI_PORT` | Puerto del controlador (separado del host) | `8443` |
| `UNIFI_SITE` | Nombre del sitio (visible en la URL del panel) | `default` |
| `UNIFI_USER` | Username de la cuenta local creada en el Paso 1 | `api_service` |
| `UNIFI_PASSWORD` | Contraseña de esa cuenta | `mi_contraseña_segura` |
| `VERIFY_SSL` | Verificación de certificado SSL | `false` |
| `UNIFI_OS` | `true` para UDM/UCG/Cloud Key Gen2+, `false` para instalación legacy | `false` |
| `ACLR_MODEL` | Cadena del modelo del AP a filtrar | `U7LR` |

> **Importante — `UNIFI_HOST` no debe incluir el puerto.** El puerto se configura
> por separado en `UNIFI_PORT`. Si se incluye el puerto dentro de `UNIFI_HOST`
> (p. ej. `https://192.168.1.10:8443`), la URL resultante quedará duplicada
> como `https://192.168.1.10:8443:8443` y el controlador rechazará la conexión.

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Comprobación de disponibilidad del servicio |
| `GET` | `/debug/devices` | Lista todos los dispositivos con su modelo real |
| `GET` | `/ap-aclr` | Lista todos los APs que coincidan con el modelo configurado |
| `GET` | `/ap-aclr/{mac}` | Detalle completo de un AP por su dirección MAC |
| `GET` | `/ap-aclr/{mac}/clients` | Clientes inalámbricos conectados a ese AP |
| `POST` | `/ap-aclr/{mac}/rename` | Renombra un AP |
| `POST` | `/ap-aclr/{mac}/restart` | Envía un comando de reinicio al AP |
| `POST` | `/ap-aclr/{mac}/led` | Controla el LED del AP (on / off / default) |

### Ejemplos de uso con `curl`

```bash
# Verificar que el servicio está activo
curl http://localhost:6000/health

# Ver todos los dispositivos y sus modelos reales
curl http://localhost:6000/debug/devices | python3 -m json.tool

# Listar todos los APs del modelo configurado
curl http://localhost:6000/ap-aclr | python3 -m json.tool

# Obtener detalle de un AP específico por MAC
curl http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97 | python3 -m json.tool

# Ver clientes conectados a ese AP
curl http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/clients | python3 -m json.tool

# Renombrar el AP
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/rename \
  -H "Content-Type: application/json" \
  -d '{"name": "AP-Oficina-Principal"}'

# Reiniciar el AP
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/restart

# Apagar el LED del AP
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
  -d '{"led_override": "off"}'
```
## AUTENTICACIÓN CON AUTH KEY
Autenticación mediante API Key
Para proteger los endpoints sensibles del API (principalmente los métodos POST que realizan cambios en los dispositivos), se implementó un mecanismo de autenticación basado en API Key.
#¿Cómo funciona?
La API Key es un valor secreto que el cliente debe enviar en cada solicitud dentro de la cabecera HTTP:
X-API-Key: <202603>
El servidor valida este valor antes de procesar la petición. Si la clave es incorrecta o no se envía, el acceso es rechazado.
#Implementación
Se utiliza APIKeyHeader de FastAPI para capturar la cabecera:
"api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)"
Luego se valida con una función:
"async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="No autorizado")"
Esta función se aplica como dependencia en los endpoints protegidos y en todos los post definidos:
"@app.post("/ap-aclr/{mac}/rename", dependencies=[Security(verify_api_key)])"
De esta forma, cualquier solicitud a ese endpoint requiere autenticación previa.

##¿Por qué usar API Key?
Evita accesos no autorizados
Protege operaciones críticas (reinicios, cambios de configuración)
Es simple de implementar y eficiente para APIs internas

##Pruebas con curl
Ejemplo
curl -X POST http://localhost:8000/ap-aclr/aa:bb:cc:dd:ee:ff/rename \
-H "Content-Type: application/json" \
-H "X-API-Key: 202603" \
-d '{"name": "Nuevo-AP"}'

---

## Solución de problemas

### Error `api.err.Invalid` (HTTP 400) al hacer login

Este error significa que el controlador rechazó las credenciales. Pasos para diagnosticar:

**1. Verificar que las variables llegan correctamente al contenedor:**
```bash
docker exec unifi-aclr-api env | grep -E "UNIFI|ACLR"
```
Confirma que `UNIFI_USER`, `UNIFI_PASSWORD` y `UNIFI_HOST` tienen los valores esperados.

**2. Verificar que `UNIFI_HOST` no incluye el puerto:**
```
# Correcto
UNIFI_HOST=https://10.203.64.6
UNIFI_PORT=8443

# Incorrecto — genera URL duplicada https://10.203.64.6:8443:8443
UNIFI_HOST=https://10.203.64.6:8443
```

**3. Confirmar las credenciales manualmente con curl desde el host:**
```bash
curl -k -X POST https://10.203.64.6:8443/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "api_service", "password": "tu_contraseña"}'
```
Si esto devuelve `{"meta":{"rc":"ok"},...}` las credenciales son correctas.
Si devuelve `api.err.Invalid`, el problema es el usuario o la contraseña en el
controlador — verifica que la cuenta existe y que "Remote Access" está desmarcado.

**4. Revisar los logs de arranque del contenedor:**
```bash
docker logs unifi-aclr-api | head -20
```
Al arrancar, el servicio imprime la configuración activa (sin la contraseña):
```
INFO: === Configuración activa ===
INFO:   BASE_URL       : https://10.203.64.6:8443
INFO:   LOGIN_ENDPOINT : /api/login
INFO:   UNIFI_USER     : api_service
...
```
Esto permite confirmar que la URL y el usuario son los esperados antes de revisar
otras posibles causas.

---

### El endpoint `/ap-aclr` devuelve `count: 0`

El controlador responde bien pero no se encuentran dispositivos. La causa habitual
es que `ACLR_MODEL` no coincide con el modelo real que reporta el controlador.

```bash
curl http://localhost:6000/debug/devices | python3 -m json.tool
```

Busca el campo `"model"` de tu dispositivo y actualiza el `.env`:
```env
ACLR_MODEL=U7LR
```
Luego reinicia el contenedor: `docker restart unifi-aclr-api`.

---

### El contenedor no puede alcanzar el controlador UniFi

Si el contenedor corre en la **misma máquina** que el controlador UniFi, recuerda
que `localhost` dentro del contenedor apunta al propio contenedor, no al host.
Debes usar la IP de la interfaz de red del host en la LAN:

```env
# Incorrecto cuando controlador y contenedor están en el mismo host
UNIFI_HOST=https://localhost

# Correcto — IP real del host en la red local
UNIFI_HOST=https://192.168.1.10
```

---

## Referencia de puertos según tipo de instalación

| Tipo de instalación | `UNIFI_HOST` | `UNIFI_PORT` | `UNIFI_OS` |
|---------------------|-------------|--------------|------------|
| UniFi Network Application legacy (Linux/Windows) | `https://<ip>` | `8443` | `false` |
| UDM Pro / UCG Max / Cloud Key Gen2+ | `https://<ip>` | `443` | `true` |
| UniFi OS Server dedicado | `https://<ip>` | `11443` | `true` |

---

## Notas técnicas

- **Certificado SSL:** el controlador usa un certificado autofirmado por defecto.
  Mantén `VERIFY_SSL=false` a menos que hayas instalado un certificado de confianza.
- **Sesión:** la autenticación es basada en cookies. El wrapper re-autentica
  automáticamente si la sesión expira (respuesta HTTP 401).
- **Seguridad:** el endpoint `/debug/devices` expone información de red. Elimínalo
  o protégelo con autenticación antes de usar esta API en un entorno de producción.
- **Modelo del dispositivo:** el UniFi U7 LR (Wi-Fi 7) reporta el modelo como `U7LR`,
  mientras que el UAP-AC-LR (Wi-Fi 5) reporta `UAP-AC-LR`. Son generaciones distintas
  de hardware. Verifica siempre con `/debug/devices`.
- **Docker y red local:** cuando el contenedor corre en la misma máquina que el
  controlador UniFi, usa la IP de la interfaz de red del host en `UNIFI_HOST`,
  nunca `localhost`.


  ## ANEXOS
  ## Captura API funcionando Localmente
  <img width="1422" height="657" alt="image" src="https://github.com/user-attachments/assets/c11e1031-08c1-40f3-a01b-cd5b1c016c23" />
  <img width="1707" height="1086" alt="image" src="https://github.com/user-attachments/assets/b75593b4-98c1-4023-aa7d-c815f46469de" />

  ## Capturas CURL
<img width="1387" height="56" alt="image" src="https://github.com/user-attachments/assets/dbd554f5-8d6f-4b43-88cc-a0675a298375" />
<img width="1429" height="535" alt="image" src="https://github.com/user-attachments/assets/e4d65beb-2383-4136-b767-1f1ccceecb9f" />
<img width="1417" height="66" alt="image" src="https://github.com/user-attachments/assets/d21ecdc4-bf26-46a2-91c2-dbeef8307a17" />
<img width="884" height="560" alt="image" src="https://github.com/user-attachments/assets/368b33ff-a6e4-40f7-9e95-9fa92da20ec6" />

## Captura Docker funcionando
<img width="800" height="306" alt="image" src="https://github.com/user-attachments/assets/32e34323-e518-4244-99dc-f5313c56553a" />
<img width="2168" height="426" alt="image" src="https://github.com/user-attachments/assets/2b9a234e-2984-492a-800b-87eb745ce3d7" />

## Captura nivel público 





