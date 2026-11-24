# Daily updates preserve server credentials and never seed operational data.
# Add -Initialize ONLY for a new database after uploading reviewed server env files.
param(
    [Parameter(Mandatory = $true)]
    [string]$SshHost,
    [string]$SshUser = "root",
    [Parameter(Mandatory = $true)]
    [string]$ApiDomain,
    [string]$AdminDomain = "",
    [string]$RemoteDir = "/opt/zxd-pro",
    [switch]$Initialize
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if ($SshHost -notmatch '^[a-zA-Z0-9.-]+$' -or $SshUser -notmatch '^[a-zA-Z0-9_-]+$' -or $RemoteDir -notmatch '^/[a-zA-Z0-9_./-]+$') {
    throw "Invalid SSH target or remote directory."
}
if ($ApiDomain -match '^https?://') { $ApiBase = $ApiDomain.TrimEnd("/") }
else { $ApiBase = "https://$ApiDomain".TrimEnd("/") }
$ApiUri = [Uri]$ApiBase
if (-not $ApiUri.IsAbsoluteUri -or $ApiUri.Scheme -ne "https" -or $ApiUri.AbsolutePath -ne "/" -or $ApiUri.Query -or $ApiUri.Fragment -or $ApiUri.UserInfo) {
    throw "ApiDomain must be an HTTPS origin without a path."
}

function Assert-NativeSuccess([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE)." }
}

Write-Host "==> Build admin-web ($ApiBase/api)"
$PreviousApiBase = $env:VITE_API_BASE
Push-Location (Join-Path $Root "admin-web")
try {
    $env:VITE_API_BASE = "$ApiBase/api"
    npm run build
    Assert-NativeSuccess "Admin build"
} finally {
    $env:VITE_API_BASE = $PreviousApiBase
    Pop-Location
}

Write-Host "==> Create code tarball (server env, certificates and persistent data are preserved)"
$Tar = Join-Path $env:TEMP ("zxd-pro-deploy-" + [Guid]::NewGuid().ToString("N") + ".tar.gz")
Push-Location $Root
try {
    tar -czf $Tar `
        --exclude=./.git `
        --exclude=./.env* `
        --exclude=./backend/.venv `
        --exclude=./backend/.env `
        --exclude=./backend/.env.docker `
        --exclude=./backend/*.db* `
        --exclude=./backend/*.log `
        --exclude=./backend/__pycache__ `
        --exclude=./backend/certs `
        --exclude=./backend/cert `
        --exclude=./backend/data `
        --exclude=./backend/uploads `
        --exclude=./admin-web/.env* `
        --exclude=./admin-web/node_modules `
        --exclude=./miniprogram/node_modules `
        .
    Assert-NativeSuccess "Create archive"
} finally { Pop-Location }

$Target = "${SshUser}@${SshHost}"
try {
    ssh $Target "mkdir -p '$RemoteDir' && test -s '$RemoteDir/backend/.env' && test -s '$RemoteDir/.env.docker'"
    Assert-NativeSuccess "Check existing server configuration (upload reviewed env files first)"
    scp $Tar "${Target}:${RemoteDir}/zxd-pro-deploy.tar.gz"
    Assert-NativeSuccess "Upload archive"

    $RemoteCmd = @'
set -euo pipefail
cd '__REMOTE_DIR__'
tar -xzf zxd-pro-deploy.tar.gz
if ! command -v docker >/dev/null; then bash deploy/install-docker-ubuntu.sh; fi
bash deploy/run-production.sh __INITIALIZE__
mkdir -p /var/www/zxd-admin
cp -r admin-web/dist/. /var/www/zxd-admin/
'@
    $InitArg = if ($Initialize) { "--initialize" } else { "" }
    $RemoteCmd = $RemoteCmd.Replace("__REMOTE_DIR__", $RemoteDir).Replace("__INITIALIZE__", $InitArg)
    $RemoteCmd | ssh $Target "bash -s"
    Assert-NativeSuccess "Remote deployment"
} finally {
    Remove-Item -LiteralPath $Tar -Force -ErrorAction SilentlyContinue
}

Write-Host "Deployment passed. Existing server credentials and business configuration were retained."
Write-Host "Configure Nginx using deploy/configure-nginx.sh; API_DOMAIN=$($ApiUri.Host)"
if ($AdminDomain) { Write-Host "ADMIN_DOMAIN=$AdminDomain" }
