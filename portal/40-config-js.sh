#!/bin/sh
# Genera config.js al arrancar con la URL de la API recibida en $API_URL.
# API_URL vacío = misma origen (cuando el portal y la API van detrás del balanceador).
echo "window.APP_CONFIG = { API_URL: \"${API_URL:-}\" };" > /usr/share/nginx/html/config.js
echo "config.js generado con API_URL=${API_URL:-<misma origen>}"
