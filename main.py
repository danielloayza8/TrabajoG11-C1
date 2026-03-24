"""
UniFi AP AC-LR — Wrapper REST API
==================================
Servicio FastAPI que se autentica en un controlador UniFi Network local
usando una cuenta de administrador LOCAL (sin MFA) y expone endpoints para
consultar y gestionar únicamente los dispositivos UAP-AC-LR / U7LR.

Estrategia de autenticación
----------------------------
  • Se utiliza una cuenta de administrador LOCAL de UniFi (no una cuenta SSO/nube de Ubiquiti).
  • Las cuentas locales no están sujetas al requisito de MFA impuesto por Ubiquiti desde julio 2024.
  • El wrapper mantiene una única sesión autenticada (basada en cookies) y
    se re-autentica automáticamente cuando la sesión expira (HTTP 401).

Requisitos
----------
    pip install fastapi uvicorn httpx python-dotenv

Ejecución
---------
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

#Importar para implementar auth API key
from fastapi.security import APIKeyHeader
from fastapi import Security

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
load_dotenv()  # lee el archivo .env si existe — en Docker las vars vienen del --env-file

UNIFI_HOST     = os.getenv("UNIFI_HOST", "https://192.168.1.1")   # IP o hostname del controlador (sin barra final, sin puerto)
UNIFI_PORT     = os.getenv("UNIFI_PORT", "8443")                   # 443 para UniFi OS, 8443 para instalación legacy
UNIFI_SITE     = os.getenv("UNIFI_SITE", "default")                # nombre del sitio en el controlador
UNIFI_USER     = os.getenv("UNIFI_USER", "api_service")            # usuario administrador LOCAL
UNIFI_PASSWORD = os.getenv("UNIFI_PASSWORD", "changeme")           # contraseña del administrador LOCAL
VERIFY_SSL     = os.getenv("VERIFY_SSL", "false").lower() == "true"

# Los dispositivos UniFi OS (UDM/UCG) prefijan todas las llamadas a la API de red con /proxy/network.
# Los controladores legacy (instalación propia) NO usan este prefijo.
# Establece UNIFI_OS=true en tu .env si usas UDM/UCG/Cloud Key Gen2+.
IS_UNIFI_OS    = os.getenv("UNIFI_OS", "false").lower() == "true"

# BASE_URL: se limpia UNIFI_HOST de barras finales para evitar duplicar el puerto
# si el usuario incluyó el puerto dentro de UNIFI_HOST por error.
_host_clean    = UNIFI_HOST.rstrip("/")
BASE_URL       = f"{_host_clean}:{UNIFI_PORT}"

API_PREFIX     = "/proxy/network" if IS_UNIFI_OS else ""
LOGIN_ENDPOINT = "/api/login" if IS_UNIFI_OS else "/api/login"

# Cadena del modelo reportada por UniFi para el punto de acceso objetivo.
# Se usa coincidencia parcial insensible a mayúsculas, por lo que variantes como
# "UAP-AC-LR", "uap-ac-lr" o "U7LR" son reconocidas correctamente.
ACLR_MODEL     = os.getenv("ACLR_MODEL", "UAP-AC-LR")

#VARIABLES para API KEY
API_KEY = os.getenv("API_KEY", "202603")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gestor de sesión UniFi
# ---------------------------------------------------------------------------
class UniFiSession:
    """Mantiene una sesión httpx autenticada contra el controlador UniFi."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def _build_client(self) -> httpx.AsyncClient:
        """Crea y devuelve un nuevo cliente HTTP asíncrono."""
        return httpx.AsyncClient(
            base_url=BASE_URL,
            verify=VERIFY_SSL,
            timeout=10.0,
            follow_redirects=True,
        )

    async def _login(self, client: httpx.AsyncClient) -> None:
        """
        Envía las credenciales al endpoint de login y almacena la cookie de sesión.

        El controlador legacy de UniFi acepta el campo 'username' con el nombre
        de usuario local. Si la cuenta fue creada sin vincular a la nube de Ubiquiti,
        el campo username corresponde exactamente al valor de UNIFI_USER en el .env.
        Se registra en el log qué usuario y URL se están usando para facilitar la
        depuración de errores 400 por credenciales incorrectas.
        """
        payload = {"username": UNIFI_USER, "password": UNIFI_PASSWORD}
        log.info("Intentando login en %s%s como usuario '%s'", BASE_URL, LOGIN_ENDPOINT, UNIFI_USER)
        response = await client.post(
            LOGIN_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Error de autenticación en UniFi: HTTP {response.status_code} — {response.text}"
            )
        log.info("Sesión UniFi autenticada correctamente.")

    async def get_client(self) -> httpx.AsyncClient:
        """Devuelve un cliente autenticado, creándolo o re-autenticándolo si es necesario."""
        async with self._lock:
            if self._client is None:
                client = await self._build_client()
                await self._login(client)
                self._client = client
        return self._client

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Realiza una petición autenticada, reintentando una vez si recibe un 401."""
        client = await self.get_client()
        response = await client.request(method, path, **kwargs)

        if response.status_code == 401:
            log.warning("Sesión expirada — re-autenticando…")
            async with self._lock:
                await self._login(client)
            response = await client.request(method, path, **kwargs)

        return response

    async def close(self) -> None:
        """Cierra el cliente HTTP y libera la sesión."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Instancia singleton de la sesión
unifi = UniFiSession()


# ---------------------------------------------------------------------------
# Ciclo de vida de FastAPI
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Registrar la configuración activa al iniciar (sin mostrar la contraseña)
    log.info("=== Configuración activa ===")
    log.info("  BASE_URL       : %s", BASE_URL)
    log.info("  LOGIN_ENDPOINT : %s", LOGIN_ENDPOINT)
    log.info("  UNIFI_SITE     : %s", UNIFI_SITE)
    log.info("  UNIFI_USER     : %s", UNIFI_USER)
    log.info("  UNIFI_OS       : %s", IS_UNIFI_OS)
    log.info("  ACLR_MODEL     : %s", ACLR_MODEL)
    log.info("  VERIFY_SSL     : %s", VERIFY_SSL)
    log.info("============================")

    # Autenticar al inicio para que la primera petición sea rápida
    try:
        await unifi.get_client()
    except Exception as exc:
        log.error("No se pudo conectar al controlador UniFi al iniciar: %s", exc)
    yield
    await unifi.close()


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------
app = FastAPI(
    title="UniFi AP API",
    description=(
        "Wrapper ligero sobre la API REST del controlador UniFi Network, "
        "enfocado exclusivamente en los puntos de acceso UAP-AC-LR / U7LR."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------
def api_url(path: str) -> str:
    """Construye la URL completa del endpoint de la API para el sitio configurado."""
    return f"{API_PREFIX}/api/s/{UNIFI_SITE}{path}"


def filter_aclr(devices: list[dict]) -> list[dict]:
    """Filtra y devuelve únicamente los dispositivos que coincidan con ACLR_MODEL (insensible a mayúsculas)."""
    needle = ACLR_MODEL.lower()
    return [d for d in devices if needle in d.get("model", "").lower()]


def slim_device(d: dict) -> dict:
    """Devuelve un subconjunto limpio y útil de los campos de un dispositivo."""
    return {
        "id":           d.get("_id"),
        "name":         d.get("name"),
        "model":        d.get("model"),
        "mac":          d.get("mac"),
        "ip":           d.get("ip"),
        "version":      d.get("version"),
        "state":        d.get("state"),        # 1 = conectado, 0 = desconectado
        "uptime":       d.get("uptime"),        # segundos activo
        "last_seen":    d.get("last_seen"),     # timestamp Unix
        "clients":      d.get("num_sta", 0),   # clientes conectados actualmente
        "tx_bytes":     d.get("tx_bytes"),
        "rx_bytes":     d.get("rx_bytes"),
        "satisfaction": d.get("satisfaction"), # puntuación de calidad del canal (0-100)
        "radio_table":  d.get("radio_table"),   # información detallada de las radios
    }


async def _fetch_devices_raw() -> list[dict]:
    """Obtiene todos los dispositivos del controlador UniFi y los devuelve como lista de dicts."""
    resp = await unifi.request("GET", api_url("/stat/device"))
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Error en la API de UniFi: {resp.text}",
        )
    body = resp.json()
    return body.get("data", [])

# Función de validación
async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="No autorizado")


# ---------------------------------------------------------------------------
# Modelos Pydantic para los cuerpos POST
# ---------------------------------------------------------------------------

class RenamePayload(BaseModel):
    name: str           # nuevo nombre para el dispositivo

class LEDPayload(BaseModel):
    led_override: str   # valores posibles: "on" | "off" | "default"

class RadioPayload(BaseModel):
    radio: str          # interfaz de radio: "ng" (2.4 GHz) o "na" (5 GHz)
    channel: int        # número de canal — 0 para selección automática
    tx_power_mode: str  # "auto", "high", "medium", "low" o "custom"
    tx_power: int = 0   # potencia en dBm, solo aplica cuando tx_power_mode es "custom"

class KickClientPayload(BaseModel):
    client_mac: str     # dirección MAC del cliente WiFi a desconectar del AP


# ---------------------------------------------------------------------------
# Función auxiliar compartida por los endpoints POST que modifican un dispositivo
# ---------------------------------------------------------------------------
async def _get_device_id(mac: str) -> tuple[str, str]:
    """
    Busca el dispositivo por MAC entre los APs filtrados y devuelve (mac_lower, device_id).
    Lanza HTTP 404 si no se encuentra ningún UAP-AC-LR con esa MAC.
    """
    raw = await _fetch_devices_raw()
    devices = filter_aclr(raw)
    mac_lower = mac.lower()
    match = next((d for d in devices if d.get("mac", "").lower() == mac_lower), None)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún UAP-AC-LR con MAC {mac}",
        )
    return mac_lower, match["_id"]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
async def health():
    """Comprobación de disponibilidad — NO realiza peticiones al controlador UniFi."""
    return {"status": "ok"}


@app.get("/debug/devices", tags=["Debug"])
async def debug_all_devices():
    """
    Devuelve TODOS los dispositivos registrados en UniFi (cualquier modelo) con su nombre,
    MAC y modelo — útil para verificar qué cadena de modelo reporta tu AP.
    Elimina o protege este endpoint en producción.
    """
    raw = await _fetch_devices_raw()
    return {
        "total": len(raw),
        "aclr_filter_string": ACLR_MODEL,
        "devices": [
            {
                "name":  d.get("name"),
                "mac":   d.get("mac"),
                "model": d.get("model"),
                "type":  d.get("type"),
            }
            for d in raw
        ],
    }


@app.get("/ap-aclr", tags=["AP AC-LR"])
async def list_aclr_devices():
    """
    Lista todos los puntos de acceso UAP-AC-LR / U7LR registrados en este sitio.

    Devuelve un resumen limpio de cada dispositivo: estado de conectividad,
    número de clientes, puntuación de satisfacción e información de radios.
    """
    raw = await _fetch_devices_raw()
    devices = filter_aclr(raw)
    return {
        "count": len(devices),
        "devices": [slim_device(d) for d in devices],
    }


@app.get("/ap-aclr/{mac}", tags=["AP AC-LR"])
async def get_aclr_device(mac: str):
    """
    Obtiene información detallada de un único UAP-AC-LR identificado por su dirección MAC.

    La MAC debe estar en formato minúsculas separada por dos puntos, p. ej. `aa:bb:cc:dd:ee:ff`.
    """
    raw = await _fetch_devices_raw()
    devices = filter_aclr(raw)
    mac_lower = mac.lower()
    match = next((d for d in devices if d.get("mac", "").lower() == mac_lower), None)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún UAP-AC-LR con MAC {mac}",
        )
    # Devuelve los datos completos del dispositivo tal como los reporta UniFi
    return match


@app.get("/ap-aclr/{mac}/clients", tags=["AP AC-LR"])
async def get_aclr_clients(mac: str):
    """
    Lista los clientes inalámbricos actualmente asociados a un UAP-AC-LR específico.
    """
    resp = await unifi.request("GET", api_url("/stat/sta"))
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    all_clients: list[dict] = resp.json().get("data", [])
    mac_lower = mac.lower()
    # Filtra solo los clientes cuyo ap_mac coincida con el AP solicitado
    ap_clients = [
        c for c in all_clients if c.get("ap_mac", "").lower() == mac_lower
    ]
    return {"ap_mac": mac_lower, "count": len(ap_clients), "clients": ap_clients}


# ---------------------------------------------------------------------------
# Endpoints POST — operaciones de escritura (no reinician el AP)
# ---------------------------------------------------------------------------

<<<<<<< HEAD
@app.post("/ap-aclr/{mac}/rename", tags=["AP AC-LR — Escritura"])
=======
@app.post("/ap-aclr/{mac}/rename", dependencies=[Security(verify_api_key)], tags=["AP AC-LR — Escritura"])
>>>>>>> origin/devcpaguay
async def rename_aclr_device(mac: str, payload: RenamePayload):
    """
    Renombra un dispositivo UAP-AC-LR.

    El cambio es inmediato y no interrumpe el servicio WiFi.

    Cuerpo: `{ "name": "nuevo-nombre" }`
    """
    _, device_id = await _get_device_id(mac)
    resp = await unifi.request(
        "PUT",
        api_url(f"/rest/device/{device_id}"),
        json={"name": payload.name},
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"success": True, "new_name": payload.name}


<<<<<<< HEAD
@app.post("/ap-aclr/{mac}/led", tags=["AP AC-LR — Escritura"])
=======
@app.post("/ap-aclr/{mac}/led", dependencies=[Security(verify_api_key)], tags=["AP AC-LR — Escritura"])
>>>>>>> origin/devcpaguay
async def set_aclr_led(mac: str, payload: LEDPayload):
    """
    Controla el estado del LED de un UAP-AC-LR.

    El cambio es inmediato y no interrumpe el servicio WiFi.

    Cuerpo: `{ "led_override": "on" | "off" | "default" }`
    """
    if payload.led_override not in ("on", "off", "default"):
        raise HTTPException(
            status_code=400,
            detail="led_override debe ser 'on', 'off' o 'default'",
        )
    _, device_id = await _get_device_id(mac)
    resp = await unifi.request(
        "PUT",
        api_url(f"/rest/device/{device_id}"),
        json={"led_override": payload.led_override},
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"success": True, "led_override": payload.led_override}


<<<<<<< HEAD
@app.post("/ap-aclr/{mac}/radio", tags=["AP AC-LR — Escritura"])
=======
@app.post("/ap-aclr/{mac}/radio", dependencies=[Security(verify_api_key)], tags=["AP AC-LR — Escritura"])
>>>>>>> origin/devcpaguay
async def set_aclr_radio(mac: str, payload: RadioPayload):
    """
    Ajusta el canal y la potencia de transmisión de una radio del AP.

    El cambio puede causar una interrupción breve de la radio afectada (1-3 segundos)
    mientras el AP cambia de canal, pero **no reinicia el dispositivo**.

    - `radio`: `"ng"` para 2.4 GHz, `"na"` para 5 GHz
    - `channel`: número de canal (1-13 para 2.4 GHz, 36-177 para 5 GHz) o `0` para auto
    - `tx_power_mode`: `"auto"` | `"high"` | `"medium"` | `"low"` | `"custom"`
    - `tx_power`: potencia en dBm, solo se usa cuando `tx_power_mode` es `"custom"`

    Cuerpo de ejemplo:
    ```json
    { "radio": "na", "channel": 36, "tx_power_mode": "auto", "tx_power": 0 }
    ```
    """
    if payload.radio not in ("ng", "na"):
        raise HTTPException(status_code=400, detail="radio debe ser 'ng' (2.4 GHz) o 'na' (5 GHz)")
    if payload.tx_power_mode not in ("auto", "high", "medium", "low", "custom"):
        raise HTTPException(status_code=400, detail="tx_power_mode debe ser 'auto', 'high', 'medium', 'low' o 'custom'")

    _, device_id = await _get_device_id(mac)

    # La API de UniFi espera una lista radio_table con el objeto de la radio a modificar.
    # Solo enviamos los campos que queremos cambiar dentro del objeto de esa radio.
    radio_entry: dict = {
        "radio":         payload.radio,
        "channel":       payload.channel,
        "tx_power_mode": payload.tx_power_mode,
    }
    if payload.tx_power_mode == "custom":
        radio_entry["tx_power"] = payload.tx_power

    resp = await unifi.request(
        "PUT",
        api_url(f"/rest/device/{device_id}"),
        json={"radio_table": [radio_entry]},
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {
        "success":       True,
        "radio":         payload.radio,
        "channel":       payload.channel,
        "tx_power_mode": payload.tx_power_mode,
        "tx_power":      payload.tx_power if payload.tx_power_mode == "custom" else "n/a",
    }


<<<<<<< HEAD
@app.post("/ap-aclr/{mac}/kick-client", tags=["AP AC-LR — Escritura"])
=======
@app.post("/ap-aclr/{mac}/kick-client", dependencies=[Security(verify_api_key)], tags=["AP AC-LR — Escritura"])
>>>>>>> origin/devcpaguay
async def kick_client(mac: str, payload: KickClientPayload):
    """
    Desconecta un cliente WiFi específico del AP.

    El cliente queda desasociado de la red pero puede volver a conectarse
    automáticamente si su dispositivo tiene reconexión automática habilitada.
    Útil para forzar que un cliente cambie de banda o renegocie su conexión.

    El parámetro `{mac}` es la MAC del **AP**; `client_mac` en el cuerpo
    es la MAC del **cliente** a desconectar.

    Cuerpo: `{ "client_mac": "aa:bb:cc:dd:ee:ff" }`
    """
    # Verificamos que el AP existe y es un UAP-AC-LR antes de ejecutar el comando
    await _get_device_id(mac)

    resp = await unifi.request(
        "POST",
        api_url("/cmd/stamgr"),
        json={"cmd": "kick-sta", "mac": payload.client_mac.lower()},
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {
        "success":    True,
        "ap_mac":     mac.lower(),
        "client_mac": payload.client_mac.lower(),
        "message":    "Cliente desconectado. Puede reconectarse automáticamente.",
<<<<<<< HEAD
    }
=======
    }
>>>>>>> origin/devcpaguay
