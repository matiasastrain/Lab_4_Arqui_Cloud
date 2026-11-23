#!/bin/sh
# Genera config.js al iniciar el contenedor, con la URL del gestor que entrega Terraform.
cat > /usr/share/nginx/html/config.js <<EOT
window.PDI_CONFIG = { API_URL: "${API_URL}", ENV_NAME: "${ENV_NAME}" };
EOT
