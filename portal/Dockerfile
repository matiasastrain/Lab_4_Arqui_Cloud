# Portal estático (equivalente a la Static Web App del diagrama). Sin dependencias.
FROM nginxinc/nginx-unprivileged:1.27-alpine

USER root
COPY index.html app.js styles.css /usr/share/nginx/html/
COPY 40-config.sh /docker-entrypoint.d/40-config.sh
RUN chmod +x /docker-entrypoint.d/40-config.sh \
 && touch /usr/share/nginx/html/config.js \
 && chown 101:101 /usr/share/nginx/html/config.js
USER 101

ENV PORT=8080
EXPOSE 8080
