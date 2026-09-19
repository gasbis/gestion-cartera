# syntax=docker/dockerfile:1
#
# Adaptado del Dockerfile que ya usas para otra app Reflex en Railway:
# mismo enfoque (Caddy sirviendo el frontend estático + proxy al
# backend, todo por un único puerto), cambiando solo la instalación de
# dependencias a uv (pyproject.toml/uv.lock, no requirements.txt) y la
# imagen base a Python 3.14 (lo que pide este proyecto).
FROM python:3.14-slim
ARG PORT=8080
# URL pública por la que el NAVEGADOR llega a la app (el frontend la
# necesita para saber a qué URL de websocket conectar). En Railway: la
# URL del dominio generado para este servicio -- ver notas de
# despliegue en el README. Se define en las dos variantes de nombre
# que ha usado Reflex según la versión (API_URL / REFLEX_API_URL), por
# si acaso.
ARG API_URL
ENV PORT=$PORT \
    API_URL=${API_URL:-http://localhost:$PORT} \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} \
    PYTHONUNBUFFERED=1
RUN apt-get update -y && apt-get install -y caddy unzip curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY Caddyfile .
COPY . .

# Instala las dependencias con uv, usando el mismo pyproject.toml/
# uv.lock que en local. --frozen falla si uv.lock no está actualizado:
# hay que correr `uv sync` en local tras tocar pyproject.toml y subir
# el uv.lock resultante antes de desplegar.
RUN pip install --no-cache-dir uv
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"

RUN reflex init
RUN reflex export --frontend-only --no-zip && mv .web/build/client/* /srv/ && rm -rf .web
STOPSIGNAL SIGKILL
EXPOSE $PORT
CMD [ -d alembic ] && reflex db migrate; \
	caddy start && reflex run --env prod --backend-only --loglevel debug
