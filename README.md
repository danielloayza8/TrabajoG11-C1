# UniFi AP — Wrapper REST API

Wrapper ligero con FastAPI sobre la API REST del controlador UniFi Network local,
enfocado exclusivamente en los puntos de acceso **UAP-AC-LR**.

Puede ejecutarse directamente con Python o dentro de un contenedor Docker.

---

## Índice

1. [Requisitos previos](#requisitos-previos)
2. [Crear cuenta de administrador local](#paso-1--crear-una-cuenta-de-administrador-local)
3. [Ejecución con Python](#paso-2--ejecución-directa-con-python)
4. [Ejecución con Docker](#paso-3--ejecución-con-docker)
5. [Variables de entorno](#variables-de-entorno)
6. [Endpoints disponibles](#endpoints-disponibles)
7. [Uso detallado de los endpoints POST](#uso-detallado-de-los-endpoints-post)
8. [Solución de problemas](#solución-de-problemas)
9. [Referencia de puertos](#referencia-de-puertos-según-tipo-de-instalación)
10. [Notas técnicas](#notas-técnicas)

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
- **Convención de red interna:** el sufijo `.local` indica que este recurso no existe fuera de la LAN.
- **Mantenibilidad:** evita confusiones si otro administrador revisa la lista de cuentas en el futuro.
- **Seguridad:** al no apuntar a ningún dominio real, se elimina cualquier riesgo de filtración.

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
   - `Site Administrator` — necesario para los endpoints POST (renombrar, radio, LED, kick).
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

### Construir la imagen

```bash
# Desde la carpeta raíz del proyecto (donde está el Dockerfile)
# Ejecutar SIEMPRE tras cualquier cambio en main.py
docker build -t unifi-aclr-api:latest .
```

> **Importante:** cada vez que se modifique `main.py` hay que reconstruir la imagen
> con `docker build` antes de relanzar el contenedor. Si no se reconstruye, el
> contenedor seguirá ejecutando el código anterior aunque el archivo haya cambiado.

### Ejecutar el contenedor

```bash
docker run -d \
  --name unifi-aclr-api \
  --restart unless-stopped \
  --env-file .env \
  -p 6000:6000 \
  unifi-aclr-api:latest
```

### Reconstruir y redesplegar en un solo comando

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
# Ver los logs en tiempo real
docker logs -f unifi-aclr-api

# Ver solo las últimas 30 líneas
docker logs unifi-aclr-api --tail 30

# Verificar las variables de entorno que recibe el contenedor
docker exec unifi-aclr-api env | grep -E "UNIFI|ACLR"

# Detener el contenedor
docker stop unifi-aclr-api

# Reiniciar (necesario tras cambiar el .env, NO tras cambiar main.py)
docker restart unifi-aclr-api
```

---

## Variables de entorno

Estas variables se configuran en el archivo `.env`.

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `UNIFI_HOST` | IP o hostname del controlador (sin barra final, **sin puerto**) | `https://<tu-ip>` |
| `UNIFI_PORT` | Puerto del controlador (separado del host) | `8443` |
| `UNIFI_SITE` | Nombre del sitio (visible en la URL del panel) | `default` |
| `UNIFI_USER` | Username de la cuenta local creada en el Paso 1 | `api_service` |
| `UNIFI_PASSWORD` | Contraseña de esa cuenta — **sin comillas** | `mi_password_seguro` |
| `VERIFY_SSL` | Verificación de certificado SSL | `false` |
| `UNIFI_OS` | `true` para UDM/UCG/Cloud Key Gen2+, `false` para instalación legacy | `false` |
| `ACLR_MODEL` | Cadena del modelo del AP a filtrar | `U7LR` |

### Reglas importantes para el archivo `.env`

El archivo `.env` tiene reglas de sintaxis que pueden causar errores silenciosos
si no se respetan, especialmente cuando Docker lee el archivo directamente:

```env
# CORRECTO — sin comillas, sin caracteres especiales
UNIFI_PASSWORD=mipassword123

# PROBLEMA — Docker pasa las comillas dobles como parte del valor
UNIFI_PASSWORD="mipassword"   # el controlador recibe: "mipassword" (con comillas)

# PROBLEMA — el símbolo # inicia un comentario, la contraseña se trunca
UNIFI_PASSWORD=mipass#word    # el controlador recibe solo: mipass

# PROBLEMA — el símbolo $ se intenta expandir como variable de entorno
UNIFI_PASSWORD=mipass$word    # puede resultar en: mipass (si $word no existe)

# PROBLEMA — UNIFI_HOST no debe incluir el puerto
UNIFI_HOST=https://<tu-ip>:8443  # genera URL duplicada: https://<tu-ip>:8443:8443
```

> **Recomendación:** usa una contraseña con solo letras, números y guiones bajos
> para la cuenta de servicio de la API. No hay beneficio de seguridad adicional
> en usar caracteres especiales en una cuenta de servicio local de red interna.

---

## Endpoints disponibles

### Lectura (GET)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Comprobación de disponibilidad del servicio |
| `GET` | `/debug/devices` | Lista todos los dispositivos con su modelo real |
| `GET` | `/ap-aclr` | Lista todos los APs que coincidan con el modelo configurado |
| `GET` | `/ap-aclr/{mac}` | Detalle completo de un AP por su dirección MAC |
| `GET` | `/ap-aclr/{mac}/clients` | Clientes inalámbricos conectados a ese AP |

### Escritura (POST) — ninguno reinicia el AP

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/ap-aclr/{mac}/rename` | Renombra el AP |
| `POST` | `/ap-aclr/{mac}/led` | Controla el LED (on / off / default) |
| `POST` | `/ap-aclr/{mac}/radio` | Cambia canal y potencia de una radio |
| `POST` | `/ap-aclr/{mac}/kick-client` | Desconecta un cliente WiFi del AP |

> Todos los POST están diseñados para no interrumpir el servicio WiFi del AP.
> El endpoint `/radio` puede causar una pausa breve (1-3 segundos) en la radio
> afectada mientras el AP cambia de canal, pero **no reinicia el dispositivo**.

---

## Uso detallado de los endpoints POST

Hay dos formas de invocar los endpoints POST: con **curl** desde la terminal,
o con la **interfaz Swagger UI** que FastAPI genera automáticamente.

### Swagger UI (recomendado para probar)

Abre `http://localhost:6000/docs` en el navegador. Verás todos los endpoints
listados. Para ejecutar uno:

1. Haz clic sobre el endpoint POST que quieras usar.
2. Haz clic en **"Try it out"** (esquina superior derecha del panel).
3. Completa el campo `mac` con la dirección MAC del AP.
4. Edita el cuerpo JSON en el campo **"Request body"** con tus valores.
5. Haz clic en **"Execute"** y revisa la respuesta en el panel inferior.

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
  -d '{"led_override": "off"}'

# Encender el LED
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
  -d '{"led_override": "on"}'

# Restaurar comportamiento normal
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
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
| `radio` | string | `"ng"` / `"na"` | `"ng"` = radio 2.4 GHz, `"na"` = radio 5 GHz |
| `channel` | entero | `0` o número de canal | `0` = selección automática por el controlador |
| `tx_power_mode` | string | `"auto"` `"high"` `"medium"` `"low"` `"custom"` | Modo de potencia. Con `"custom"` se usa el campo `tx_power` |
| `tx_power` | entero | dBm (ej. `14`–`23`) | Solo aplica cuando `tx_power_mode` es `"custom"`. En otro caso usar `0` |

**Canales recomendados:**

- **2.4 GHz (`"ng"`):** canales 1, 6 o 11 (no se solapan entre sí)
- **5 GHz (`"na"`):** canales 36, 40, 44, 48, 149, 153, 157, 161 (UNII-1 y UNII-3)

**Con curl:**

```bash
# Cambiar la radio de 5 GHz al canal 36 con potencia automática
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -d '{"radio": "na", "channel": 36, "tx_power_mode": "auto", "tx_power": 0}'

# Cambiar la radio de 2.4 GHz al canal 1 con potencia automática
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -d '{"radio": "ng", "channel": 1, "tx_power_mode": "auto", "tx_power": 0}'

# Cambiar la radio de 5 GHz al canal 149 con potencia personalizada de 20 dBm
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
  -d '{"radio": "na", "channel": 149, "tx_power_mode": "custom", "tx_power": 20}'

# Dejar que el controlador seleccione el canal automáticamente
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/radio \
  -H "Content-Type: application/json" \
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
- Forzar que un cliente cambie de la banda 2.4 GHz a la de 5 GHz.
- Liberar una conexión "pegada" que tiene mala señal pero no se reconecta.
- Aplicar cambios de VLAN o política sin esperar a que el cliente se desconecte solo.

> El parámetro `{mac}` en la URL es la **MAC del AP**.
> El campo `client_mac` en el cuerpo es la **MAC del cliente** a desconectar.
> Son dos dispositivos distintos — no confundirlos.

**Cuerpo requerido:**

```json
{
  "client_mac": "aa:bb:cc:dd:ee:ff"
}
```

**Cómo obtener la MAC de un cliente:** usa el endpoint GET de clientes del AP:

```bash
# Primero obtener la lista de clientes conectados al AP
curl http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/clients | python3 -m json.tool
```

Busca el campo `"mac"` del cliente que quieres desconectar en la respuesta.

**Con curl:**

```bash
# Desconectar el cliente con MAC aa:bb:cc:dd:ee:ff del AP
curl -X POST http://localhost:6000/ap-aclr/fc:ec:da:3d:7f:97/kick-client \
  -H "Content-Type: application/json" \
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

## Solución de problemas

### Error `api.err.Invalid` (HTTP 400) al hacer login

Este error significa que el controlador rechazó las credenciales.

**Causa más frecuente con Docker:** la contraseña en el `.env` tiene comillas que
`python-dotenv` elimina automáticamente al usar uvicorn, pero que Docker pasa
literalmente al proceso cuando usa `--env-file`. El código incluye una función
`_strip_quotes` que elimina comillas envolventes, pero si la contraseña tiene
caracteres especiales como `#` o `$` el problema persiste.

**Diagnóstico paso a paso:**

```bash
# 1. Ver los logs de arranque — muestran la config activa y la longitud de la contraseña
docker logs unifi-aclr-api | head -20
```

El log muestra `PASSWORD_LEN: N caracteres`. Si el número no coincide con la
longitud real de tu contraseña, las comillas u otros caracteres están siendo
incluidos como parte del valor.

```bash
# 2. Verificar las variables en el contenedor
docker exec unifi-aclr-api env | grep UNIFI_PASSWORD
```

```bash
# 3. Confirmar las credenciales directamente con curl desde el host
curl -k -X POST https://<tu-ip>:8443/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "api_service", "password": "tu_password"}'
```

Si responde `{"meta":{"rc":"ok"}}` las credenciales son correctas y el problema
está en cómo se pasan al contenedor. Si responde `api.err.Invalid`, el problema
está en el controlador — verifica que la cuenta existe y que "Remote Access" está desmarcado.

**Solución definitiva:** usa una contraseña sin caracteres especiales en el `.env`:

```env
UNIFI_PASSWORD=mipassword_seguro_123
```

---

### El endpoint `/ap-aclr` devuelve `count: 0`

El login funciona pero no se encuentran dispositivos. La causa habitual es que
`ACLR_MODEL` no coincide con el modelo real del AP.

```bash
curl http://localhost:6000/debug/devices | python3 -m json.tool
```

Busca el campo `"model"` en la respuesta y actualiza el `.env`. Luego reinicia:

```bash
docker restart unifi-aclr-api
```

---

### El contenedor no puede alcanzar el controlador

Si el contenedor y el controlador están en la **misma máquina**, `localhost` dentro
del contenedor apunta al propio contenedor. Usa la IP real del host en la red local:

```env
# Incorrecto
UNIFI_HOST=https://localhost

# Correcto
UNIFI_HOST=https://<tu-ip>
```

---

### Cambié el `.env` pero el comportamiento no cambió

- Si cambiaste una variable de entorno → `docker restart unifi-aclr-api`
- Si cambiaste `main.py` → debes reconstruir la imagen completa:

```bash
docker build -t unifi-aclr-api:latest . && \
docker rm -f unifi-aclr-api && \
docker run -d --name unifi-aclr-api --restart unless-stopped \
  --env-file .env -p 6000:6000 unifi-aclr-api:latest
```

---

## Referencia de puertos según tipo de instalación

| Tipo de instalación | `UNIFI_HOST` | `UNIFI_PORT` | `UNIFI_OS` |
|---------------------|-------------|--------------|------------|
| UniFi Network Application legacy (Linux/Windows) | `https://<tu-ip>` | `8443` | `false` |
| UDM Pro / UCG Max / Cloud Key Gen2+ | `https://<tu-ip>` | `443` | `true` |
| UniFi OS Server dedicado | `https://<tu-ip>` | `11443` | `true` |

---

## Notas técnicas

- **Certificado SSL:** el controlador usa un certificado autofirmado por defecto.
  Mantén `VERIFY_SSL=false` a menos que hayas instalado un certificado de confianza.
- **Sesión:** la autenticación es basada en cookies. El wrapper re-autentica
  automáticamente si la sesión expira (respuesta HTTP 401).
- **Seguridad:** el endpoint `/debug/devices` expone información de red. Elimínalo
  o protégelo con autenticación antes de usar esta API en un entorno de producción.
- **Comillas en Docker:** `python-dotenv` elimina comillas de los valores del `.env`
  automáticamente; Docker con `--env-file` no lo hace. El código incluye la función
  `_strip_quotes` que normaliza este comportamiento, pero la solución más robusta es
  usar contraseñas sin caracteres especiales ni comillas.
- **Modelo del dispositivo:** el U7 LR (Wi-Fi 7) reporta `U7LR`; el UAP-AC-LR
  (Wi-Fi 5) reporta `UAP-AC-LR`. Verifica siempre con `/debug/devices`.
