# UniFi AP — Wrapper REST API

Wrapper ligero con FastAPI sobre la API REST del controlador UniFi Network local,
enfocado en la gestión de puntos de acceso **UAP-AC-LR** y **UAP-AC-LITE**.

Puede ejecutarse directamente con Python o dentro de un contenedor Docker.

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Crear cuenta de administrador local](#2-crear-cuenta-de-administrador-local)
   - [¿Por qué es necesario?](#por-qué-es-necesario)
   - [¿Por qué el campo Email usa `api@local`?](#por-qué-el-campo-email-usa-apilocal)
   - [Pasos para crear la cuenta](#pasos-para-crear-la-cuenta)
3. [Ejecución con Python](#3-ejecución-con-python)
4. [Ejecución con Docker](#4-ejecución-con-docker)
   - [Construir la imagen](#construir-la-imagen)
   - [Ejecutar el contenedor](#ejecutar-el-contenedor)
   - [Reconstruir y redesplegar](#reconstruir-y-redesplegar)
   - [Comandos útiles de gestión](#comandos-útiles-de-gestión)
5. [Variables de entorno](#5-variables-de-entorno)
   - [Reglas importantes para el archivo `.env`](#reglas-importantes-para-el-archivo-env)
6. [Endpoints disponibles](#6-endpoints-disponibles)
   - [Lectura (GET)](#lectura-get)
   - [Escritura (POST)](#escritura-post)
7. [Uso detallado de los endpoints POST](#7-uso-detallado-de-los-endpoints-post)
   - [Swagger UI](#swagger-ui-recomendado-para-probar)
   - [rename — Renombrar el AP](#post-ap-aclrmacrename--renombrar-el-ap)
   - [led — Controlar el LED](#post-ap-aclrmacled--controlar-el-led)
   - [radio — Cambiar canal y potencia](#post-ap-aclrmacradio--cambiar-canal-y-potencia-de-radio)
   - [kick-client — Desconectar un cliente](#post-ap-aclrmackick-client--desconectar-un-cliente-wifi)
8. [Autenticación con API Key](#8-autenticación-con-api-key)
9. [Soporte para múltiples modelos de AP](#9-soporte-para-múltiples-modelos-de-ap)
10. [Apertura de puertos con DST-NAT en MikroTik](#10-apertura-de-puertos-con-dst-nat-en-mikrotik-l009uigs-rm)
11. [Solución de problemas](#11-solución-de-problemas)
    - [Error `api.err.Invalid` (HTTP 400)](#error-apierrinvalid-http-400-al-hacer-login)
    - [El endpoint devuelve `count: 0`](#el-endpoint-ap-aclr-devuelve-count-0)
    - [El contenedor no alcanza el controlador](#el-contenedor-no-puede-alcanzar-el-controlador)
    - [Cambié el `.env` pero no cambió nada](#cambié-el-env-pero-el-comportamiento-no-cambió)
12. [Referencia de puertos](#12-referencia-de-puertos-según-tipo-de-instalación)
13. [Notas técnicas](#13-notas-técnicas)
14. [Capturas de funcionamiento](#14-capturas-de-funcionamiento)

---

## 1. Requisitos previos

- Python 3.11+ **o** Docker instalado
- UniFi Network Application en ejecución (instalación propia en Linux/Windows)
- Una cuenta de administrador **local** en el controlador (ver [sección 2](#2-crear-cuenta-de-administrador-local))

---

## 2. Crear cuenta de administrador local

> ⚠️ **IMPORTANTE — Este paso soluciona el problema del MFA**

### ¿Por qué es necesario?

Desde julio de 2024, Ubiquiti exige autenticación multifactor (MFA) en todas las
cuentas vinculadas a la nube (cuentas SSO de Ubiquiti). Esto rompe cualquier proceso
de login automatizado, ya que el segundo factor requiere intervención humana y no
puede ser resuelto por un script o servicio.

La solución es crear una cuenta de administrador **estrictamente local**: una cuenta
que vive únicamente dentro del controlador UniFi, **sin estar vinculada a ninguna
cuenta de Ubiquiti**. Este tipo de cuenta no tiene MFA y se autentica únicamente con
usuario y contraseña, permitiendo el acceso programático sin interrupciones.

### ¿Por qué el campo Email usa `api@local`?

El formulario de creación de administradores en UniFi solicita un campo de **Email**.
Sin embargo, cuando la cuenta es local (sin vínculo a la nube), este campo **no es
verificado ni utilizado para ningún propósito real**: no se envía correo de
confirmación, no se valida el dominio, y no se usa para el login.

Se recomienda `api@local` o `servicio@local` por las siguientes razones:

| Razón | Explicación |
|-------|-------------|
| **Claridad operacional** | Deja claro que es una cuenta de servicio, no de una persona real |
| **Convención de red interna** | El sufijo `.local` indica que el recurso no existe fuera de la LAN |
| **Mantenibilidad** | Evita confusiones si otro administrador revisa la lista de cuentas |
| **Seguridad** | Al no apuntar a ningún dominio real, elimina riesgos de filtración |

> Lo que **sí importa** para el login es el campo **Username**, que es el valor que
> debes colocar en `UNIFI_USER` dentro del archivo `.env`.
> El campo Email es completamente irrelevante para la autenticación local.

### Pasos para crear la cuenta

1. Accede a la interfaz web del controlador en `https://<tu-ip>:8443`
2. Ve a **Settings → Admins**
3. Haz clic en **+** para agregar un nuevo administrador
4. Completa los campos:
   - **Email**: `api@local` *(cualquier formato email válido — no se verifica)*
   - **Username**: `api_service` *(valor que irá en `UNIFI_USER`)*
5. Marca **"Set Admin Password"** y establece una contraseña segura
6. **Desmarca "Remote Access"** — paso crítico: deja la cuenta como local pura sin MFA
7. Asigna el rol:
   - `View Only` — para endpoints GET (solo lectura)
   - `Site Administrator` — para endpoints POST (renombrar, radio, LED, kick)
8. Guarda y verifica el acceso con las nuevas credenciales

---

## 3. Ejecución con Python

```bash
# 1. Entra a la carpeta del proyecto
cd unifi_aclr_api

# 2. Crea un entorno virtual
python -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate

# 3. Instala las dependencias
pip install -r requirements.txt

# 4. Crea el archivo de configuración
cp .env.example .env
# Edita .env y completa los valores reales

# 5. Inicia el servidor
uvicorn main:app --host 0.0.0.0 --port 6000 --reload
```

La documentación interactiva estará disponible en: **http://localhost:6000/docs**

---

## 4. Ejecución con Docker

### Construir la imagen

```bash
# Ejecutar SIEMPRE tras cualquier cambio en main.py
docker build -t unifi-aclr-api:latest .
```

> **Importante:** cada vez que se modifique `main.py` hay que reconstruir la imagen
> antes de relanzar el contenedor. Si no se reconstruye, el contenedor seguirá
> ejecutando el código anterior aunque el archivo haya cambiado en disco.

### Ejecutar el contenedor

Las credenciales se inyectan en tiempo de ejecución con `--env-file` y **nunca
deben estar dentro de la imagen**.

```bash
docker run -d \
  --name unifi-aclr-api \
  --restart unless-stopped \
  --env-file .env \
  -p 6000:6000 \
  unifi-aclr-api:latest
```

### Reconstruir y redesplegar

```bash
docker build -t unifi-aclr-api:latest . && \
docker rm -f unifi-aclr-api && \
docker run -d \
  --name unifi-aclr-api \
  --restart unless-stopped \
  --env-file .env \
  -p 6000:6000 \
  unifi-aclr-api:latest
```

### Comandos útiles de gestión

```bash
# Ver logs en tiempo real
docker logs -f unifi-aclr-api

# Ver las últimas 30 líneas
docker logs unifi-aclr-api --tail 30

# Verificar variables de entorno en el contenedor
docker exec unifi-aclr-api env | grep -E "UNIFI|ACLR"

# Detener el contenedor
docker stop unifi-aclr-api

# Reiniciar (solo tras cambiar .env, NO tras cambiar main.py)
docker restart unifi-aclr-api
```

---

## 5. Variables de entorno

Estas variables se configuran en el archivo `.env` y se pasan al contenedor con `--env-file`.

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `UNIFI_HOST` | IP o hostname del controlador *(sin barra final, **sin puerto**)* | `https://<tu-ip>` |
| `UNIFI_PORT` | Puerto del controlador *(separado del host)* | `8443` |
| `UNIFI_SITE` | Nombre del sitio *(visible en la URL del panel)* | `default` |
| `UNIFI_USER` | Username de la cuenta local creada en el [Paso 2](#2-crear-cuenta-de-administrador-local) | `api_service` |
| `UNIFI_PASSWORD` | Contraseña de esa cuenta — **sin comillas** | `mi_password_seguro` |
| `VERIFY_SSL` | Verificación de certificado SSL | `false` |
| `UNIFI_OS` | `true` para UDM/UCG/Cloud Key Gen2+, `false` para instalación legacy | `false` |
| `AP_MODELS` | Modelos de AP a filtrar, separados por coma | `U7LR,UAP-AC-LR,UAP-AC-LITE` |
| `API_KEY` | Clave secreta para autenticar los endpoints POST | `mi_api_key_secreta` |

### Reglas importantes para el archivo `.env`

El archivo `.env` tiene reglas de sintaxis que pueden causar errores silenciosos,
especialmente cuando Docker lee el archivo con `--env-file`:

```env
# ✅ CORRECTO — sin comillas, sin caracteres especiales
UNIFI_PASSWORD=mipassword123

# ❌ PROBLEMA — Docker pasa las comillas dobles como parte del valor
UNIFI_PASSWORD="mipassword"      # el controlador recibe: "mipassword" (con comillas)

# ❌ PROBLEMA — el símbolo # inicia un comentario, la contraseña se trunca
UNIFI_PASSWORD=mipass#word       # el controlador recibe solo: mipass

# ❌ PROBLEMA — el símbolo $ se expande como variable de entorno
UNIFI_PASSWORD=mipass$word       # puede resultar en: mipass

# ❌ PROBLEMA — UNIFI_HOST no debe incluir el puerto
UNIFI_HOST=https://<tu-ip>:8443  # genera URL duplicada: https://<tu-ip>:8443:8443
```

> **Recomendación:** usa una contraseña con solo letras, números y guiones bajos
> para la cuenta de servicio. No hay beneficio adicional en usar caracteres especiales
> en una cuenta de servicio local de red interna.

---

## 6. Endpoints disponibles

### Lectura (GET)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Comprobación de disponibilidad del servicio |
| `GET` | `/debug/devices` | Lista todos los dispositivos con su modelo real |
| `GET` | `/ap-aclr` | Lista todos los APs que coincidan con los modelos configurados |
| `GET` | `/ap-aclr/{mac}` | Detalle completo de un AP por su dirección MAC |
| `GET` | `/ap-aclr/{mac}/clients` | Clientes inalámbricos conectados a ese AP |

### Escritura (POST)

> Ninguno de estos endpoints reinicia el AP.

| Método | Ruta | Descripción | Requiere API Key |
|--------|------|-------------|:---:|
| `POST` | `/ap-aclr/{mac}/rename` | Renombra el AP | ✅ |
| `POST` | `/ap-aclr/{mac}/led` | Controla el LED (on / off / default) | ✅ |
| `POST` | `/ap-aclr/{mac}/radio` | Cambia canal y potencia de una radio | ✅ |
| `POST` | `/ap-aclr/{mac}/kick-client` | Desconecta un cliente WiFi del AP | ✅ |

> El endpoint `/radio` puede causar una pausa breve de 1-3 segundos en la radio
> afectada mientras el AP cambia de canal, pero **no reinicia el dispositivo**.

---

## 7. Uso detallado de los endpoints POST

### Swagger UI (recomendado para probar)

Abre `http://localhost:6000/docs` en el navegador para acceder a la interfaz
interactiva generada automáticamente por FastAPI:

1. Haz clic sobre el endpoint POST que quieras usar
2. Haz clic en **"Try it out"** *(esquina superior derecha del panel)*
3. Completa el campo `mac` con la dirección MAC del AP
4. Edita el cuerpo JSON en **"Request body"** con tus valores
5. Haz clic en **"Execute"** y revisa la respuesta en el panel inferior

> Recuerda incluir la cabecera `X-API-Key` en cada solicitud POST.
> En Swagger UI puedes configurarla haciendo clic en el botón **"Authorize"** (🔒).

---

### `POST /ap-aclr/{mac}/rename` — Renombrar el AP

Cambia el nombre visible del AP en el panel de UniFi. El cambio es inmediato
y no afecta la conectividad de los clientes.

**Cuerpo requerido:**

```json
{
  "name": "nuevo-nombre"
}
```

**Con curl:**

```bash
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/rename \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"name": "AP-Sala-Principal"}'
```

**Respuesta esperada:**

```json
{
  "success": true,
  "new_name": "AP-Sala-Principal"
}
```

---

### `POST /ap-aclr/{mac}/led` — Controlar el LED

Activa, apaga o restaura el comportamiento predeterminado del LED del AP.
El cambio es inmediato y no afecta la conectividad.

**Cuerpo requerido:**

```json
{
  "led_override": "off"
}
```

| Valor | Efecto |
|-------|--------|
| `"on"` | LED siempre encendido |
| `"off"` | LED siempre apagado |
| `"default"` | Comportamiento predeterminado (parpadea según estado) |

**Con curl:**

```bash
# Apagar el LED
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"led_override": "off"}'

# Encender el LED
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"led_override": "on"}'

# Restaurar comportamiento normal
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"led_override": "default"}'
```

**Respuesta esperada:**

```json
{
  "success": true,
  "led_override": "off"
}
```

---

### `POST /ap-aclr/{mac}/radio` — Cambiar canal y potencia de radio

Ajusta el canal WiFi y la potencia de transmisión de una radio específica del AP.
Puede causar una interrupción breve (1-3 segundos) en esa radio mientras el AP
cambia de canal, pero **no reinicia el dispositivo completo**.

**Cuerpo requerido:**

```json
{
  "radio": "na",
  "channel": 36,
  "tx_power_mode": "auto",
  "tx_power": 0
}
```

| Campo | Tipo | Valores válidos | Descripción |
|-------|------|----------------|-------------|
| `radio` | string | `"ng"` / `"na"` | `"ng"` = 2.4 GHz · `"na"` = 5 GHz |
| `channel` | entero | `0` o número de canal | `0` = selección automática por el controlador |
| `tx_power_mode` | string | `"auto"` `"high"` `"medium"` `"low"` `"custom"` | Con `"custom"` se usa el campo `tx_power` |
| `tx_power` | entero | dBm (ej. `14`–`23`) | Solo aplica cuando `tx_power_mode` es `"custom"` |

**Canales recomendados:**

- **2.4 GHz (`"ng"`):** canales `1`, `6` o `11` — no se solapan entre sí
- **5 GHz (`"na"`):** canales `36`, `40`, `44`, `48`, `149`, `153`, `157`, `161` (UNII-1 y UNII-3)

**Con curl:**

```bash
# Radio 5 GHz → canal 36, potencia automática
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"radio": "na", "channel": 36, "tx_power_mode": "auto", "tx_power": 0}'

# Radio 2.4 GHz → canal 1, potencia automática
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"radio": "ng", "channel": 1, "tx_power_mode": "auto", "tx_power": 0}'

# Radio 5 GHz → canal 149, potencia personalizada de 20 dBm
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"radio": "na", "channel": 149, "tx_power_mode": "custom", "tx_power": 20}'

# Canal automático
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"radio": "na", "channel": 0, "tx_power_mode": "auto", "tx_power": 0}'
```

**Respuesta esperada:**

```json
{
  "success": true,
  "radio": "na",
  "channel": 36,
  "tx_power_mode": "auto",
  "tx_power": "n/a"
}
```

---

### `POST /ap-aclr/{mac}/kick-client` — Desconectar un cliente WiFi

Desconecta un cliente específico del AP. El cliente queda desasociado pero puede
volver a conectarse automáticamente si su dispositivo tiene reconexión habilitada.

**Cuándo es útil:**

- Forzar que un cliente migre de la banda 2.4 GHz a la de 5 GHz
- Liberar una conexión "pegada" con mala señal que no se reconecta sola
- Aplicar cambios de VLAN o política sin esperar a la desconexión natural

> ⚠️ El `{mac}` en la URL es la **MAC del AP**.
> El `client_mac` en el cuerpo es la **MAC del cliente** a desconectar.
> Son dos dispositivos distintos — no confundirlos.

**Cómo obtener la MAC del cliente:**

```bash
# Listar clientes conectados al AP para obtener su MAC
curl http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/clients | python3 -m json.tool
```

**Cuerpo requerido:**

```json
{
  "client_mac": "aa:bb:cc:dd:ee:ff"
}
```

**Con curl:**

```bash
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/kick-client \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"client_mac": "aa:bb:cc:dd:ee:ff"}'
```

**Respuesta esperada:**

```json
{
  "success": true,
  "ap_mac": "fc:ec:da:3d:7f:97",
  "client_mac": "aa:bb:cc:dd:ee:ff",
  "message": "Cliente desconectado. Puede reconectarse automáticamente."
}
```

---

## 8. Autenticación con API Key

Para proteger los endpoints POST que realizan cambios en los dispositivos, se
implementó autenticación mediante **API Key**.

### ¿Cómo funciona?

El cliente debe enviar la clave secreta en cada solicitud dentro de la cabecera HTTP:

```
X-API-Key: <tu_api_key>
```

El servidor valida este valor antes de procesar la petición. Si la clave es
incorrecta o no se envía, el acceso es rechazado con `HTTP 403 Forbidden`.

### ¿Por qué usar API Key?

- Evita accesos no autorizados desde Internet o la red local
- Protege operaciones sensibles (cambios de canal, configuración, desconexión de clientes)
- Simple de implementar y eficiente para APIs internas
- Especialmente importante si el puerto está expuesto con port forwarding

### Configuración

Define la clave en el archivo `.env`:

```env
API_KEY=mi_api_key_secreta_larga
```

### Implementación en el código

Se utiliza `APIKeyHeader` de FastAPI para capturar la cabecera:

```python
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="No autorizado")
```

Esta función se aplica como dependencia en todos los endpoints POST:

```python
@app.post("/ap-aclr/{mac}/rename", dependencies=[Security(verify_api_key)])
```

### Ejemplo con curl incluyendo la API Key

```bash
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/rename \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_secreta" \
  -d '{"name": "Nuevo-AP"}'
```

---

## 9. Soporte para múltiples modelos de AP

Se implementó soporte para gestionar múltiples modelos de Access Point UniFi de
forma simultánea, en lugar de limitarse a un único modelo como en la versión inicial.

### ¿Cómo funciona?

La variable de entorno `AP_MODELS` acepta una lista de modelos separados por coma.
La API carga esta lista al iniciar y realiza un filtrado dinámico de los dispositivos
obtenidos desde el controlador UniFi.

```env
AP_MODELS=U7LR,UAP-AC-LR,UAP-AC-LITE
```

### Ventajas

- Filtra múltiples modelos simultáneamente en una sola consulta
- No requiere cambios en el código al agregar nuevos modelos
- Mantiene compatibilidad con distintos entornos de red donde coexisten varios
  tipos de hardware

### Agregar un nuevo modelo

Simplemente añade el modelo al final de `AP_MODELS` en el `.env` y reinicia
el contenedor:

```env
# Antes
AP_MODELS=U7LR,UAP-AC-LR

# Después de añadir el UAP-AC-LITE
AP_MODELS=U7LR,UAP-AC-LR,UAP-AC-LITE
```

Usa el endpoint [`/debug/devices`](#lectura-get) para verificar el nombre exacto
del modelo que reporta tu controlador antes de añadirlo.

---

## 10. Apertura de puertos con DST-NAT en MikroTik (L009UiGS-RM)

Para permitir el acceso externo a los servicios internos, se configuraron reglas de
**DST-NAT (Destination Network Address Translation)** en el router MikroTik L009UiGS-RM.

El DST-NAT redirige solicitudes que llegan desde Internet en un puerto específico
del router hacia una dirección IP y puerto interno de la red local.

### Servicios expuestos

#### Servicio 1 — API propia (puerto `6000` TCP)

Permite acceder desde Internet a la API desarrollada localmente. El tráfico entrante
en el puerto público es redirigido al servidor interno donde corre el contenedor Docker.

El puerto es **TCP puro** — HTTP opera sobre TCP y uvicorn escucha en un socket TCP
estándar. No se requiere UDP.

#### Servicio 2 — UniFi Network Application (puerto `8443` TCP)

Expone el servicio de UniFi Network Application y su API REST para pruebas remotas
e integración durante el desarrollo.

### Acceso externo

Los servicios pueden accederse mediante la **IP pública** del router o el
**dominio DDNS generado por MikroTik**, lo que permite acceder sin necesidad de
conocer cambios en la IP pública:

```bash
# Por IP pública
http://<IP_PUBLICA>:<PUERTO>

# Por dominio MikroTik DDNS
http://<DOMINIO_MIKROTIK>:<PUERTO>
```

> ⚠️ Si expones la API a Internet, asegúrate de tener la [autenticación por API Key](#8-autenticación-con-api-key)
> activada. Sin ella, cualquier persona con acceso al puerto puede modificar la
> configuración de los APs.

---

## 11. Solución de problemas

### Error `api.err.Invalid` (HTTP 400) al hacer login

El controlador rechazó las credenciales.

**Causa más frecuente con Docker:** la contraseña en el `.env` tiene comillas que
`python-dotenv` elimina automáticamente al usar uvicorn, pero que Docker pasa
literalmente al proceso con `--env-file`. El código incluye `_strip_quotes` para
manejar este caso, pero caracteres como `#` o `$` siguen siendo problemáticos.

**Diagnóstico:**

```bash
# 1. Ver configuración activa y longitud de la contraseña al arrancar
docker logs unifi-aclr-api | head -20
```

El log muestra `PASSWORD_LEN: N caracteres`. Si el número no coincide con la
longitud real de tu contraseña, hay caracteres extra (comillas u otros) incluidos.

```bash
# 2. Verificar las variables en el contenedor
docker exec unifi-aclr-api env | grep UNIFI_PASSWORD

# 3. Confirmar credenciales directamente desde el host
curl -k -X POST https://<tu-ip>:8443/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "api_service", "password": "tu_password"}'
```

Si responde `{"meta":{"rc":"ok"}}` las credenciales son correctas y el problema
está en cómo Docker las pasa. Si responde `api.err.Invalid`, verifica en el panel
de UniFi que la cuenta existe y que "Remote Access" está desmarcado.

**Solución definitiva:**

```env
UNIFI_PASSWORD=mipassword_seguro_123
```

---

### El endpoint `/ap-aclr` devuelve `count: 0`

El login funciona pero no se encuentran dispositivos. Causa habitual: `AP_MODELS`
no coincide con el modelo real que reporta el controlador.

```bash
curl http://localhost:6000/debug/devices | python3 -m json.tool
```

Busca el campo `"model"` en la respuesta, actualiza `AP_MODELS` en el `.env`
y reinicia:

```bash
docker restart unifi-aclr-api
```

---

### El contenedor no puede alcanzar el controlador

Si el contenedor y el controlador están en la **misma máquina**, `localhost`
dentro del contenedor apunta al propio contenedor, no al host.

```env
# ❌ Incorrecto cuando ambos están en el mismo host
UNIFI_HOST=https://localhost

# ✅ Correcto — IP real del host en la red local
UNIFI_HOST=https://<tu-ip>
```

---

### Cambié el `.env` pero el comportamiento no cambió

| Qué cambiaste | Qué hacer |
|---------------|-----------|
| Variable en `.env` | `docker restart unifi-aclr-api` |
| Código en `main.py` | Reconstruir la imagen completa (ver abajo) |

```bash
docker build -t unifi-aclr-api:latest . && \
docker rm -f unifi-aclr-api && \
docker run -d --name unifi-aclr-api --restart unless-stopped \
  --env-file .env -p 6000:6000 unifi-aclr-api:latest
```

---

## 12. Referencia de puertos según tipo de instalación

| Tipo de instalación | `UNIFI_HOST` | `UNIFI_PORT` | `UNIFI_OS` |
|---------------------|-------------|:------------:|:----------:|
| UniFi Network Application legacy (Linux/Windows) | `https://<tu-ip>` | `8443` | `false` |
| UDM Pro / UCG Max / Cloud Key Gen2+ | `https://<tu-ip>` | `443` | `true` |
| UniFi OS Server dedicado | `https://<tu-ip>` | `11443` | `true` |

---

## 13. Notas técnicas

- **Certificado SSL:** el controlador usa certificado autofirmado por defecto.
  Mantén `VERIFY_SSL=false` salvo que tengas un certificado de confianza instalado.
- **Sesión:** la autenticación es basada en cookies. El wrapper re-autentica
  automáticamente cuando la sesión expira (respuesta HTTP 401).
- **Endpoint de debug:** `/debug/devices` expone información de red. Elimínalo o
  protégelo antes de usar la API en producción.
- **Comillas en Docker:** `python-dotenv` elimina comillas del `.env` automáticamente;
  Docker con `--env-file` no lo hace. La función `_strip_quotes` normaliza este
  comportamiento, pero la solución más robusta es evitar caracteres especiales.
- **Modelos de dispositivo:** el U7 LR (Wi-Fi 7) reporta `U7LR`; el UAP-AC-LR
  (Wi-Fi 5) reporta `UAP-AC-LR`; el UAP-AC-LITE reporta `UAP-AC-LITE`.
  Verifica siempre con `/debug/devices`.
- **Red local con Docker:** usa la IP de la interfaz de red del host en `UNIFI_HOST`,
  nunca `localhost`.

---

## 14. Capturas de funcionamiento

### API funcionando localmente

<img width="1422" alt="API local - vista general" src="https://github.com/user-attachments/assets/c11e1031-08c1-40f3-a01b-cd5b1c016c23" />

<img width="1707" alt="API local - detalle de respuesta" src="https://github.com/user-attachments/assets/b75593b4-98c1-4023-aa7d-c815f46469de" />

---

### Pruebas con curl

<img width="1387" alt="curl - health check" src="https://github.com/user-attachments/assets/dbd554f5-8d6f-4b43-88cc-a0675a298375" />

<img width="1429" alt="curl - listado de APs" src="https://github.com/user-attachments/assets/e4d65beb-2383-4136-b767-1f1ccceecb9f" />

<img width="1417" alt="curl - endpoint POST" src="https://github.com/user-attachments/assets/d21ecdc4-bf26-46a2-91c2-dbeef8307a17" />

<img width="884" alt="curl - respuesta JSON" src="https://github.com/user-attachments/assets/368b33ff-a6e4-40f7-9e95-9fa92da20ec6" />

---

### Docker funcionando

<img width="800" alt="Docker - contenedor en ejecución" src="https://github.com/user-attachments/assets/32e34323-e518-4244-99dc-f5313c56553a" />

<img width="2168" alt="Docker - logs de arranque" src="https://github.com/user-attachments/assets/2b9a234e-2984-492a-800b-87eb745ce3d7" />

---

### Acceso desde IP pública

<img width="1916" alt="IP pública - health check" src="https://github.com/user-attachments/assets/94a24c6e-1141-47ae-844d-7e18f0a47071" />

<img width="1907" alt="IP pública - Swagger UI" src="https://github.com/user-attachments/assets/d14679c0-3d9f-4c56-a809-707c6ce0d230" />

<img width="1879" alt="IP pública - respuesta en producción" src="https://github.com/user-attachments/assets/f08b628c-a6b2-4b6c-92ac-e4113823d53e" />
