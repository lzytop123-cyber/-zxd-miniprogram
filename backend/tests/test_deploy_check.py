import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "scripts" / "deploy_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_fails_the_same_production_cors_baseline_as_startup(checker, monkeypatch):
    from app.core.config import Settings

    config = Settings(
        _env_file=None, app_env="production", secret_key="a" * 64,
        admin_password="StrongDeployment123!", cors_origins="*",
        database_url="sqlite:///:memory:", wx_appid="", wx_pay_mchid="",
    )
    monkeypatch.setattr(checker, "settings", config)
    assert checker.main() == 1


def test_deployment_cannot_pass_using_development_configuration(checker, monkeypatch):
    from app.core.config import Settings

    config = Settings(
        _env_file=None, app_env="development", secret_key="a" * 64,
        admin_password="StrongDeployment123!", cors_origins="https://admin.example.com",
        database_url="sqlite:///:memory:", wx_appid="", wx_pay_mchid="",
    )
    monkeypatch.setattr(checker, "settings", config)
    assert checker.main() == 1
