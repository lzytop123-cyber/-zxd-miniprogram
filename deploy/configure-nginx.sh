#!/usr/bin/env bash
# 在服务器项目根目录执行：配置 Nginx 反代 API + 后台静态站
# 用法:
#   export API_DOMAIN=api.example.com
#   export ADMIN_DOMAIN=admin.example.com
#   export SSL_CERT=/etc/nginx/ssl/fullchain.pem
#   export SSL_KEY=/etc/nginx/ssl/privkey.pem
#   ./deploy/configure-nginx.sh

set -euo pipefail

API_DOMAIN="${API_DOMAIN:?set API_DOMAIN}"
ADMIN_DOMAIN="${ADMIN_DOMAIN:-}"
SSL_CERT="${SSL_CERT:-/etc/nginx/ssl/fullchain.pem}"
SSL_KEY="${SSL_KEY:-/etc/nginx/ssl/privkey.pem}"
ADMIN_ROOT="${ADMIN_ROOT:-/var/www/zxd-admin}"

if ! command -v nginx >/dev/null 2>&1; then
  apt-get update
  apt-get install -y nginx
fi

mkdir -p "$ADMIN_ROOT"
mkdir -p /etc/nginx/ssl

CONF="/etc/nginx/sites-available/zxd.conf"
cat > "$CONF" <<EOF
upstream zxd_api {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name ${API_DOMAIN};

    ssl_certificate     ${SSL_CERT};
    ssl_certificate_key ${SSL_KEY};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    gzip on;
    gzip_min_length 1024;
    gzip_comp_level 5;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;

    client_max_body_size 10m;

    location /static/ {
        proxy_pass http://zxd_api;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host \$host;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    location / {
        proxy_pass http://zxd_api;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_connect_timeout 10s;
        proxy_read_timeout 90s;
        proxy_send_timeout 90s;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

server {
    listen 80;
    server_name ${API_DOMAIN};
    return 301 https://\$host\$request_uri;
}
EOF

if [[ -n "$ADMIN_DOMAIN" ]]; then
  cat >> "$CONF" <<EOF

server {
    listen 443 ssl http2;
    server_name ${ADMIN_DOMAIN};

    ssl_certificate     ${SSL_CERT};
    ssl_certificate_key ${SSL_KEY};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    gzip on;
    gzip_min_length 1024;
    gzip_comp_level 5;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;

    root ${ADMIN_ROOT};
    index index.html;

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}

server {
    listen 80;
    server_name ${ADMIN_DOMAIN};
    return 301 https://\$host\$request_uri;
}
EOF
fi

ln -sf "$CONF" /etc/nginx/sites-enabled/zxd.conf
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t
systemctl reload nginx
echo "Nginx configured for ${API_DOMAIN}${ADMIN_DOMAIN:+ and ${ADMIN_DOMAIN}}"
