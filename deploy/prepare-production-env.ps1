# Generate backend/.env for Docker production (skip WeChat fields)
# Usage: .\deploy\prepare-production-env.ps1 -ApiBase "http://YOUR_SERVER_IP:8000"

param(
    [string]$ApiBase = "http://127.0.0.1:8000"
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Example = Join-Path $Root "backend\.env.production.example"
$DevEnv = Join-Path $Root "backend\.env"
$Target = Join-Path $Root "backend\.env.docker"

if (-not (Test-Path $Example)) {
    Write-Error "Missing $Example"
    exit 1
}

function Read-EnvMap($Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        $map[$key] = $val
    }
    return $map
}

$dev = Read-EnvMap $DevEnv
$content = Get-Content $Example -Raw -Encoding UTF8

$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$secret = [BitConverter]::ToString($bytes).Replace("-", "").ToLower()
$adminPass = "ZxdAdmin" + (Get-Random -Minimum 100000 -Maximum 999999) + "!"
$mysqlRoot = "ZxdRoot" + (Get-Random -Minimum 100000 -Maximum 999999) + "!"
$mysqlPass = "ZxdDb" + (Get-Random -Minimum 100000 -Maximum 999999) + "!"

$content = $content -replace "(?m)^SECRET_KEY=.*", "SECRET_KEY=$secret"
$content = $content -replace "(?m)^BASE_URL=.*", "BASE_URL=$ApiBase"
$content = $content -replace "(?m)^ADMIN_PASSWORD=.*", "ADMIN_PASSWORD=$adminPass"
$content = $content -replace "(?m)^DATABASE_URL=.*", "DATABASE_URL=mysql+pymysql://zxd:${mysqlPass}@mysql:3306/zxd_study?charset=utf8mb4"
$content = $content -replace "(?m)^WX_APPID=.*", "WX_APPID="
$content = $content -replace "(?m)^WX_APP_SECRET=.*", "WX_APP_SECRET="
$content = $content -replace "(?m)^WX_PAY_MCHID=.*", "WX_PAY_MCHID="
$content = $content -replace "(?m)^WX_PAY_SERIAL_NO=.*", "WX_PAY_SERIAL_NO="
$content = $content -replace "(?m)^WX_PAY_API_V3_KEY=.*", "WX_PAY_API_V3_KEY="

$copyKeys = @(
    "MEITUAN_CLIENT_ID", "MEITUAN_SECRET", "MEITUAN_SHOP_ID",
    "MEITUAN_PLATFORM", "MEITUAN_BASE_URL", "MEITUAN_TIMEOUT", "COUPON_PROVIDER",
    "TTLOCK_CLIENT_ID", "TTLOCK_CLIENT_SECRET", "TTLOCK_USERNAME", "TTLOCK_PASSWORD"
)
foreach ($key in $copyKeys) {
    if ($dev.ContainsKey($key) -and $dev[$key]) {
        $pattern = "(?m)^" + [regex]::Escape($key) + "=.*"
        $content = $content -replace $pattern, ($key + "=" + $dev[$key])
    }
}

if ($content -notmatch "(?m)^PRE_WECHAT_LAUNCH=") {
    $content = $content -replace "(?m)^(APP_ENV=production)", "`$1`r`nPRE_WECHAT_LAUNCH=true"
} else {
    $content = $content -replace "(?m)^PRE_WECHAT_LAUNCH=.*", "PRE_WECHAT_LAUNCH=true"
}

[System.IO.File]::WriteAllText($Target, $content, [System.Text.UTF8Encoding]::new($false))

# Docker Compose reads these from the same directory env / shell
$composeEnv = @(
    "MYSQL_ROOT_PASSWORD=$mysqlRoot"
    "MYSQL_PASSWORD=$mysqlPass"
) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $Root ".env.docker"), $composeEnv, [System.Text.UTF8Encoding]::new($false))

Write-Host "Upload backend/.env.docker to server as backend/.env before docker compose up."
Write-Host "Upload .env.docker (repo root) for docker compose MySQL passwords."
Write-Host "ADMIN_PASSWORD=$adminPass"
Write-Host "MYSQL_PASSWORD=$mysqlPass"
Write-Host "MYSQL_ROOT_PASSWORD=$mysqlRoot"
Write-Host "Next on Linux server:"
Write-Host "  docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build"
Write-Host "  docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/init_production.py"
