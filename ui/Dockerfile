FROM nginxinc/nginx-unprivileged:1.27.4-alpine

USER root
RUN apk upgrade --no-cache \
    && rm -rf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
RUN chown -R 101:101 /usr/share/nginx/html /etc/nginx/nginx.conf

USER 101:101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
