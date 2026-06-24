# Package and upload project to Ubuntu server (SSH password: enter when prompted)
# Usage:
#   .\deploy\deploy-to-server.ps1 -SshHost 1.2.3.4 -SshUser root -ApiDomain "api.example.com"

param(
    [Parameter(Mandatory = $true)]
    [string]$SshHost,
    [string]$SshUser = "root",
    [Parameter(Mandatory = $true)]
    [string]$ApiDomain,
    [string]$AdminDomain = "",
    [string]$RemoteDir = "/opt/zxd-pro"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ($ApiDomain -match "^https?://") {
    $ApiBase = $ApiDomain.TrimEnd("/")
} else {
    $ApiBase = "https://$ApiDomain".TrimEnd("/")
}
$ApiBaseUrl = "$ApiBase/api"
$ApiHostOnly = ($ApiBase -replace '^https?://', '')

Write-Host "==> Generate production env ($ApiBase)"
& "$Root\deploy\prepare-production-env.ps1" -ApiBase $ApiBase

Write-Host "==> Build admin-web ($ApiBaseUrl)"
$envFile = Join-Path $Root "admin-web\.env.production"
"VITE_API_BASE=$ApiBaseUrl" | Set-Content -Path $envFile -Encoding UTF8
Push-Location (Join-Path $Root "admin-web")
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

Write-Host "==> Create tarball"
$Tar = Join-Path $env:TEMP "zxd-pro-deploy.tar.gz"
if (Test-Path $Tar) { Remove-Item $Tar -Force }

Push-Location $Root
tar -czf $Tar `
    --exclude=./.git `
    --exclude=./backend/.venv `
    --exclude=./backend/*.db `
    --exclude=./backend/.env `
    --exclude=./admin-web/node_modules `
    --exclude=./miniprogram/node_modules `
    .
Pop-Location

$Target = "${SshUser}@${SshHost}"
Write-Host "==> Upload to ${Target}:${RemoteDir}"
ssh $Target "mkdir -p $RemoteDir"
scp $Tar "${Target}:${RemoteDir}/zxd-pro-deploy.tar.gz"
scp "$Root\backend\.env.docker" "${Target}:${RemoteDir}/backend.env.docker"
scp "$Root\.env.docker" "${Target}:${RemoteDir}/env.docker"

Write-Host "==> Remote deploy (enter SSH password when prompted)"
$RemoteCmd = @"
set -e
cd $RemoteDir
tar -xzf zxd-pro-deploy.tar.gz
cp backend.env.docker backend/.env
cp env.docker .env.docker
chmod +x deploy/*.sh 2>/dev/null || true
if ! command -v docker >/dev/null; then bash deploy/install-docker-ubuntu.sh; fi
docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build
for i in \$(seq 1 30); do curl -sf http://127.0.0.1:8000/health && break; sleep 2; done
curl -sf http://127.0.0.1:8000/health; echo
docker compose -f docker-compose.prod.yml --env-file .env.docker exec -T api python scripts/init_production.py
mkdir -p /var/www/zxd-admin
cp -r admin-web/dist/* /var/www/zxd-admin/
docker compose -f docker-compose.prod.yml --env-file .env.docker exec -T api python scripts/deploy_check.py || true
"@

$RemoteCmd | ssh $Target "bash -s"

Write-Host ""
Write-Host "Deploy finished."
Write-Host "Configure Nginx on server:"
Write-Host "  export API_DOMAIN=$ApiHostOnly"
if ($AdminDomain) {
    $ad = ($AdminDomain -replace '^https?://', '')
    Write-Host "  export ADMIN_DOMAIN=$ad"
}
Write-Host "  cd $RemoteDir && ./deploy/configure-nginx.sh"
Write-Host "Check ADMIN_PASSWORD / MYSQL_* from prepare-production-env output above."
