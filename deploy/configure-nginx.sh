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
}

server {
    listen 443 ssl http2;
    server_name ${API_DOMAIN};

    ssl_certificate     ${SSL_CERT};
    ssl_certificate_key ${SSL_KEY};

    client_max_body_size 10m;

    location / {
        proxy_pass http://zxd_api;
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

    root ${ADMIN_ROOT};
    index index.html;

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
