#!/usr/bin/env bash
# 知行岛 · 生产服务器准备；首次数据库初始化需显式 --initialize。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> 检查 Docker"
command -v docker >/dev/null || { echo "请先安装 Docker"; exit 1; }
docker compose version >/dev/null || { echo "请先安装 Docker Compose v2"; exit 1; }

if [[ ! -f backend/.env ]]; then
  echo "==> 生成 backend/.env"
  if [[ -f backend/.env.production.example ]]; then
    cp backend/.env.production.example backend/.env
    SECRET=$(openssl rand -hex 32)
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" backend/.env
    echo "已创建 backend/.env，请编辑：微信/云老板凭证、ADMIN_PASSWORD、BASE_URL、CORS_ORIGINS"
    echo "编辑完成后重新运行本脚本"
    exit 1
  fi
  echo "缺少 backend/.env，请先复制 .env.production.example"
  exit 1
fi

bash deploy/run-production.sh "$@"

echo
echo "完成。下一步："
echo "  1. 配置 Nginx（deploy/nginx.conf.example，可先 HTTP 再 HTTPS）"
echo "  2. admin-web: npm run build，上传 dist/ 到 /var/www/zxd-admin"
echo "  3. 微信审核通过后：填 WX_*、PRE_WECHAT_LAUNCH=false、配置小程序合法域名"
