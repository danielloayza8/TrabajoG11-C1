# UniFi AP — Wrapper REST API

Wrapper ligero con FastAPI sobre la API REST del controlador UniFi Network local,
enfocado exclusivamente en los puntos de acceso **UAP-AC-LR / U7LR**.

---

## Requisitos previos

- Python 3.11 o superior
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

Por esta razón se puede poner cualquier valor que tenga formato de email válido.
Se recomienda usar algo como `api@local` o `servicio@local` porque:

- Deja claro que es una cuenta de servicio, no de una persona real.
- El sufijo `.local` indica explícitamente que es un recurso interno de red.
- Evita confusiones si en el futuro otro administrador revisa la lista de cuentas.
- No apunta a ningún dominio real, eliminando cualquier riesgo de filtración.

Lo que **sí importa** para el login de la API es el campo **Username** (nombre de
usuario), que es el valor que debes colocar en `UNIFI_USER` dentro del archivo `.env`.

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

## Paso 2 — Instalación y configuración

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
```

### Variables de entorno (`.env`)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `UNIFI_HOST` | IP o hostname del controlador (sin barra final) | `https://192.168.1.10` |
| `UNIFI_PORT` | Puerto del controlador | `8443` |
| `UNIFI_SITE` | Nombre del sitio (visible en la URL del panel) | `default` |
| `UNIFI_USER` | Username de la cuenta local creada en el Paso 1 | `api_service` |
| `UNIFI_PASSWORD` | Contraseña de esa cuenta | `mi_contraseña_segura` |
| `VERIFY_SSL` | Verificación de certificado SSL | `false` |
| `UNIFI_OS` | `true` para UDM/UCG/Cloud Key Gen2+, `false` para instalación legacy | `false` |
| `ACLR_MODEL` | Cadena del modelo del AP a filtrar | `U7LR` |

> **Nota sobre `ACLR_MODEL`:** el modelo que reporta UniFi puede no coincidir con
> el nombre comercial del dispositivo. Usa el endpoint `/debug/devices` para
> verificar la cadena exacta que tu controlador devuelve (ver sección de depuración).

---

## Paso 3 — Ejecutar

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

La documentación interactiva (Swagger UI) estará disponible en:
**http://localhost:8000/docs**

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Comprobación de disponibilidad del servicio |
| `GET` | `/debug/devices` | Lista todos los dispositivos con su modelo real (útil para configurar `ACLR_MODEL`) |
| `GET` | `/ap-aclr` | Lista todos los APs que coincidan con el modelo configurado |
| `GET` | `/ap-aclr/{mac}` | Detalle completo de un AP por su dirección MAC |
| `GET` | `/ap-aclr/{mac}/clients` | Clientes inalámbricos conectados a ese AP |
| `POST` | `/ap-aclr/{mac}/rename` | Renombra un AP |
| `POST` | `/ap-aclr/{mac}/restart` | Envía un comando de reinicio al AP |
| `POST` | `/ap-aclr/{mac}/led` | Controla el LED del AP (on / off / default) |

### Ejemplos de uso con `curl`

```bash
# Verificar que el servicio está activo
curl http://localhost:8000/health

# Ver todos los dispositivos y sus modelos reales
curl http://localhost:8000/debug/devices | python3 -m json.tool

# Listar todos los APs del modelo configurado
curl http://localhost:8000/ap-aclr | python3 -m json.tool

# Obtener detalle de un AP específico por MAC
curl http://localhost:8000/ap-aclr/fc:ec:da:3d:7f:97 | python3 -m json.tool

# Ver clientes conectados a ese AP
curl http://localhost:8000/ap-aclr/fc:ec:da:3d:7f:97/clients | python3 -m json.tool

# Renombrar el AP
curl -X POST http://localhost:8000/ap-aclr/fc:ec:da:3d:7f:97/rename \
  -H "Content-Type: application/json" \
  -d '{"name": "AP-Oficina-Principal"}'

# Reiniciar el AP
curl -X POST http://localhost:8000/ap-aclr/fc:ec:da:3d:7f:97/restart

# Apagar el LED del AP
curl -X POST http://localhost:8000/ap-aclr/fc:ec:da:3d:7f:97/led \
  -H "Content-Type: application/json" \
  -d '{"led_override": "off"}'
```

---

## Depuración — ¿por qué `/ap-aclr` devuelve 0 dispositivos?

Si el endpoint `/ap-aclr` devuelve `{"count": 0, "devices": []}` pero sabes que
tienes APs conectados, el problema más común es que la cadena en `ACLR_MODEL` no
coincide con el modelo real que reporta el controlador.

Ejecuta el endpoint de depuración para ver el modelo exacto:

```bash
curl http://localhost:8000/debug/devices | python3 -m json.tool
```

Busca el campo `"model"` de tu dispositivo en la respuesta y actualiza tu `.env`:

```env
ACLR_MODEL=U7LR   # o el valor exacto que apareció en debug/devices
```

El filtro usa coincidencia parcial insensible a mayúsculas, así que `U7LR` también
coincidirá con `u7lr` o `U7LR-EU`.

---

## Referencia de puertos según tipo de instalación

| Tipo de instalación | Puerto | `UNIFI_OS` |
|---------------------|--------|------------|
| UniFi Network Application legacy (Linux/Windows) | `8443` | `false` |
| UDM Pro / UCG Max / Cloud Key Gen2+ | `443` | `true` |
| UniFi OS Server dedicado | `11443` | `true` |

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
  de hardware. Verifica siempre con `/debug/devices` si no estás seguro.
