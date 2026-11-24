# First-time credentials only. Existing files are never replaced.
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBase,
    [Parameter(Mandatory = $true)]
    [string]$AdminOrigin
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Example = Join-Path $Root "backend\.env.production.example"
$Target = Join-Path $Root "backend\.env.docker"
$ComposeTarget = Join-Path $Root ".env.docker"

foreach ($path in @($Target, $ComposeTarget)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to replace existing credentials: $path. Reuse the server configuration for updates."
    }
}
foreach ($origin in @($ApiBase, $AdminOrigin)) {
    $uri = [Uri]$origin
    if (-not $uri.IsAbsoluteUri -or $uri.Scheme -ne "https" -or $uri.AbsolutePath -ne "/" -or $uri.Query -or $uri.Fragment -or $uri.UserInfo) {
        throw "Specify an HTTPS origin without path, query or credentials."
    }
}
$ApiBase = $ApiBase.TrimEnd("/")
$AdminOrigin = $AdminOrigin.TrimEnd("/")

function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
}

$secret = New-Secret
$adminPass = New-Secret
$mysqlRoot = New-Secret
$mysqlPass = New-Secret
$values = @{
    SECRET_KEY = $secret
    BASE_URL = $ApiBase
    CORS_ORIGINS = $AdminOrigin
    ADMIN_PASSWORD = $adminPass
    DATABASE_URL = "mysql+pymysql://zxd:${mysqlPass}@mysql:3306/zxd_study?charset=utf8mb4"
    PRE_WECHAT_LAUNCH = "false"
}
$lines = Get-Content -LiteralPath $Example -Encoding UTF8 | ForEach-Object {
    $line = $_
    $key = ($line -split "=", 2)[0]
    if ($values.ContainsKey($key)) { "$key=$($values[$key])" } else { $line }
}
[IO.File]::WriteAllText($Target, ($lines -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
$composeEnv = "MYSQL_ROOT_PASSWORD=$mysqlRoot`nMYSQL_PASSWORD=$mysqlPass`n"
[IO.File]::WriteAllText($ComposeTarget, $composeEnv, [Text.UTF8Encoding]::new($false))

Write-Host "Created backend/.env.docker and .env.docker without printing credentials."
Write-Host "Fill real WX/provider settings and protect both files before uploading them."
Write-Host "Upload backend/.env.docker as backend/.env and root .env.docker once."
Write-Host "Future deployments reuse the existing server files."
