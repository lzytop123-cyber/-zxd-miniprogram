"""Execute deployment entry points in an isolated directory with no real services."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
BASH = Path(shutil.which("git")).resolve().parents[1] / "bin/bash.exe" if os.name == "nt" else shutil.which("bash")


@pytest.fixture
def deployment(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "deploy").mkdir()
    (tmp_path / "admin-web").mkdir()
    shutil.copy(ROOT / "backend/.env.production.example", tmp_path / "backend/.env.production.example")
    for script in ("prepare-production-env.ps1", "deploy-to-server.ps1"):
        shutil.copy(ROOT / "deploy" / script, tmp_path / "deploy" / script)
    return tmp_path


@pytest.mark.parametrize("initialize", [False, True])
def test_server_runner_never_seeds_during_daily_updates(tmp_path, initialize):
    result, log = run_server_runner(tmp_path, initialize=initialize)
    assert result.returncode == 0, result.stderr
    assert ("scripts/init_production.py" in log) is initialize
    assert "scripts/deploy_check.py" in log
    assert (tmp_path / "backend/.env").read_text() == "original-app-config"
    assert (tmp_path / ".env.docker").read_text() == "original-mysql-config"


def test_failed_preflight_stops_before_restarting_the_running_api(tmp_path):
    result, log = run_server_runner(tmp_path, fail_preflight=True)
    assert result.returncode != 0
    assert "scripts/deploy_check.py" in log
    assert "up -d" not in log


def run_server_runner(tmp_path, initialize=False, fail_preflight=False):
    if not BASH or not Path(BASH).exists():
        pytest.skip("Bash is unavailable")
    (tmp_path / "deploy").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/.env").write_text("original-app-config")
    (tmp_path / ".env.docker").write_text("original-mysql-config")
    runner = tmp_path / "deploy/run-production.sh"
    source = ROOT / "deploy/run-production.sh"
    if source.exists():
        shutil.copy(source, runner)
    driver = tmp_path / "driver.sh"
    driver.write_text('''
docker() {
    printf '%s\\n' "$*" >> "$TEST_LOG"
    if [[ "$*" == *"scripts/deploy_check.py"* && "$FAIL_PREFLIGHT" == "1" ]]; then return 7; fi
}
curl() { return 0; }
export -f docker curl
bash "$TEST_RUNNER" __INITIALIZE__
'''.replace("__INITIALIZE__", "--initialize" if initialize else ""), encoding="utf-8")
    env = dict(os.environ, TEST_RUNNER=runner.as_posix(), TEST_LOG=(tmp_path / "calls.log").as_posix(), FAIL_PREFLIGHT="1" if fail_preflight else "0")
    result = subprocess.run([str(BASH), driver.as_posix()], capture_output=True, text=True, timeout=30, env=env)
    log = tmp_path / "calls.log"
    return result, log.read_text() if log.exists() else ""


def run_powershell(script, *args):
    if not POWERSHELL:
        pytest.skip("PowerShell is unavailable")
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        capture_output=True, text=True, timeout=30,
    )


def test_prepare_preserves_existing_credentials(deployment):
    target = deployment / "backend/.env.docker"
    target.write_text("existing credentials", encoding="utf-8")
    result = run_powershell(
        deployment / "deploy/prepare-production-env.ps1",
        "-ApiBase", "https://api.example.com", "-AdminOrigin", "https://admin.example.com",
    )
    assert result.returncode != 0
    assert target.read_text(encoding="utf-8") == "existing credentials"
    assert not (deployment / ".env.docker").exists()


def test_first_time_prepare_disables_mock_and_does_not_print_secrets(deployment):
    result = run_powershell(
        deployment / "deploy/prepare-production-env.ps1",
        "-ApiBase", "https://api.example.com", "-AdminOrigin", "https://admin.example.com",
    )
    assert result.returncode == 0, result.stderr
    values = dict(
        line.split("=", 1) for line in (deployment / "backend/.env.docker").read_text(encoding="utf-8-sig").splitlines()
        if line and not line.startswith("#")
    )
    assert values["PRE_WECHAT_LAUNCH"] == "false"
    assert values["CORS_ORIGINS"] == "https://admin.example.com"
    assert values["WX_APPID"] == "wxXXXXXXXXXXXXXXXX"
    assert values["SECRET_KEY"] not in result.stdout + result.stderr
    assert values["ADMIN_PASSWORD"] not in result.stdout + result.stderr


@pytest.mark.parametrize("initialize", [False, True])
def test_update_reuses_server_env_and_initializes_only_on_request(deployment, initialize):
    driver = deployment / "driver.ps1"
    driver.write_text(r'''
$ErrorActionPreference = "Stop"
$global:remoteLog = ""
function npm { $global:LASTEXITCODE = 0 }
function tar { [IO.File]::WriteAllText($args[1], "archive"); $global:LASTEXITCODE = 0 }
function scp { $global:LASTEXITCODE = 0 }
function ssh {
    $global:remoteLog += ($args -join " ") + "`n"
    $global:remoteLog += ($input | Out-String)
    $global:LASTEXITCODE = 0
}
& "$PSScriptRoot/deploy/deploy-to-server.ps1" -SshHost example.com -ApiDomain api.example.com __INITIALIZE__
[IO.File]::WriteAllText("$PSScriptRoot/remote.log", $global:remoteLog)
'''.replace("__INITIALIZE__", "-Initialize" if initialize else ""), encoding="utf-8")
    before = {p: p.read_bytes() for p in deployment.rglob(".env*")}
    result = run_powershell(driver)
    assert result.returncode == 0, result.stderr
    remote = (deployment / "remote.log").read_text(encoding="utf-8")
    assert "test -s" in remote
    assert "bash deploy/run-production.sh --initialize" in remote if initialize else "bash deploy/run-production.sh \n" in remote.replace("\r\n", "\n")
    assert {p: p.read_bytes() for p in deployment.rglob(".env*")} == before
