# =============================================================================
# Etapa 1 — Construcción de dependencias
# =============================================================================
# Usamos una imagen completa solo para instalar y compilar las dependencias.
# Esto evita que las herramientas de compilación terminen en la imagen final.
FROM python:3.11-slim AS builder

# Directorio de trabajo para la etapa de construcción
WORKDIR /build

# Copiamos primero solo el archivo de dependencias para aprovechar la caché
# de Docker: si requirements.txt no cambia, esta capa no se reconstruye.
COPY requirements.txt .

# Instalamos las dependencias en una carpeta local aislada (no en el sistema)
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# =============================================================================
# Etapa 2 — Imagen final de producción
# =============================================================================
# Partimos de la misma imagen slim limpia, sin residuos de compilación.
FROM python:3.11-slim AS final

# Metadatos de la imagen
LABEL maintainer="api@local"
LABEL description="Wrapper REST API para puntos de acceso UniFi UAP-AC-LR / U7LR"
LABEL version="1.0.0"

# Variables de entorno del sistema
# - PYTHONDONTWRITEBYTECODE: evita generar archivos .pyc innecesarios
# - PYTHONUNBUFFERED: fuerza la salida de logs en tiempo real (importante para Docker)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Creamos un usuario sin privilegios para ejecutar la aplicación.
# Nunca se debe correr una aplicación como root dentro de un contenedor.
RUN useradd --no-create-home --shell /bin/false appuser

# Copiamos las dependencias instaladas desde la etapa de construcción
COPY --from=builder /install /usr/local

# Directorio de trabajo de la aplicación
WORKDIR /app

# Copiamos únicamente los archivos necesarios para ejecutar la API.
# El archivo .env NO se copia aquí — se inyecta en tiempo de ejecución
# mediante variables de entorno o un archivo --env-file externo.
COPY main.py .

# Asignamos la propiedad de los archivos al usuario sin privilegios
RUN chown -R appuser:appuser /app

# Cambiamos al usuario sin privilegios
USER appuser

# Puerto en el que escucha uvicorn dentro del contenedor
EXPOSE 6000

# Comando de inicio — sin --reload en producción (no hay watcher de archivos)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6000"]
