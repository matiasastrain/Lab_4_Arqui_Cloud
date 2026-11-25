FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY 40-config-js.sh /docker-entrypoint.d/40-config-js.sh
RUN chmod +x /docker-entrypoint.d/40-config-js.sh
COPY index.html app.js styles.css config.js /usr/share/nginx/html/
EXPOSE 8080
