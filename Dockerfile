# =============================================================================
# Dockerfile — RSS Digest Bot
#
# Imagen única que sirve tanto para el bot interactivo como para el
# orquestador (digest automático). El rol se selecciona vía `command` en
# docker-compose.yml o al lanzar el contenedor.
#
# Roles disponibles:
#   bot          →  python -m src.bot_runner
#   orchestrator →  supercronic /app/docker/crontab   (digest programado)
#   one-shot     →  python -m src.cli digest --dry-run
# =============================================================================

FROM python:3.14-slim

# ---------------------------------------------------------------------------
# 1. Dependencias del sistema
#    lxml y readability-lxml necesitan libxml2/libxslt en tiempo de ejecución.
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2. Supercronic — cron moderno para contenedores
#    Sin root, sin docker.sock, logs directos a stdout.
#    https://github.com/aptible/supercronic
# ---------------------------------------------------------------------------
ARG SUPERCRONIC_VERSION=v0.2.43
ARG SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64

# SHA1 del binario linux-amd64 de la versión indicada arriba.
# Para actualizarlo: descarga el binario y corre `sha1sum supercronic-linux-amd64`
# o consulta https://github.com/aptible/supercronic/releases
ARG SUPERCRONIC_SHA1SUM=f97b92132b61a8f827c3faf67106dc0e4467ccf2

RUN curl -fsSL -o /usr/local/bin/supercronic "${SUPERCRONIC_URL}" \
    && echo "${SUPERCRONIC_SHA1SUM}  /usr/local/bin/supercronic" | sha1sum -c - \
    && chmod +x /usr/local/bin/supercronic

# ---------------------------------------------------------------------------
# 3. Directorio de trabajo
# ---------------------------------------------------------------------------
WORKDIR /app

# ---------------------------------------------------------------------------
# 4. Dependencias Python (capa separada para aprovechar cache de build)
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# 5. Código fuente del proyecto
# ---------------------------------------------------------------------------
COPY src/       ./src/
COPY utils/     ./utils/
COPY docker/    ./docker/

# ---------------------------------------------------------------------------
# 6. Directorios de estado persistente
#    Vacíos en la imagen — serán sobreescritos por los bind mounts del compose.
#    Existen como fallback si se arranca el contenedor sin volúmenes.
# ---------------------------------------------------------------------------
RUN mkdir -p /app/state /app/cache

# ---------------------------------------------------------------------------
# 7. Comando por defecto: bot interactivo
#    Sobreescribir con `command:` en docker-compose para el orquestador.
# ---------------------------------------------------------------------------
CMD ["python", "-m", "src.bot_runner"]
