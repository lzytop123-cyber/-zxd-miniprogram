#!/usr/bin/env bash
# 知行岛 · 生产服务器一键准备（跳过微信，见 docs/DEPLOY.md）
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
    sed -i "s|^PRE_WECHAT_LAUNCH=.*|PRE_WECHAT_LAUNCH=true|" backend/.env 2>/dev/null || \
      sed -i "/^APP_ENV=production/a PRE_WECHAT_LAUNCH=true" backend/.env
    echo "已创建 backend/.env，请编辑：云老板凭证、ADMIN_PASSWORD、BASE_URL、域名"
    echo "编辑完成后重新运行本脚本"
    exit 0
  fi
  echo "缺少 backend/.env，请先复制 .env.production.example"
  exit 1
fi

echo "==> 启动 MySQL + Redis + API"
docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build

echo "==> 等待 API 健康检查"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -sf http://127.0.0.1:8000/health | cat
echo

echo "==> 初始化数据库（首次部署）"
read -r -p "是否运行 init_production.py？[y/N] " ans
if [[ "${ans,,}" == "y" ]]; then
  docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/init_production.py
fi

echo "==> 部署检查"
docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/deploy_check.py || true

echo
echo "完成。下一步："
echo "  1. 配置 Nginx（deploy/nginx.conf.example，可先 HTTP 再 HTTPS）"
echo "  2. admin-web: npm run build，上传 dist/ 到 /var/www/zxd-admin"
echo "  3. 微信审核通过后：填 WX_*、PRE_WECHAT_LAUNCH=false、配置小程序合法域名"
