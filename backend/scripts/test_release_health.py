import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.prod import block_mock_in_production
from app.db.session import get_db
from app.main import app
from app.services import health


class HealthReadinessTests(unittest.TestCase):
    def test_degraded_readiness_returns_503(self):
        app.dependency_overrides[get_db] = lambda: Mock()
        try:
            with patch("app.main.run_health_checks", return_value={"status": "degraded"}):
                response = TestClient(app).get("/health")
            self.assertEqual(response.status_code, 503)
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_failed_redis_makes_readiness_degraded(self):
        with patch("redis.from_url", return_value=Mock(ping=Mock(side_effect=ConnectionError))):
            result = health.run_health_checks(Mock())
        self.assertEqual(result["status"], "degraded")
        self.assertIn("redis", result["checks"])
        self.assertTrue(result["checks"]["redis"].startswith("error:"))

    def test_production_validation_rejects_mock_mode(self):
        settings = Settings(_env_file=None, app_env="production", secret_key="x" * 64,
                            admin_password="test-strong-password", cors_origins="https://admin.example.com",
                            pre_wechat_launch=True)
        with self.assertRaises(RuntimeError):
            settings.validate_for_production()

    def test_production_mock_endpoint_is_closed_even_with_legacy_flag(self):
        from fastapi import HTTPException
        with patch("app.core.prod.settings", Settings(_env_file=None, app_env="production", pre_wechat_launch=True)):
            with self.assertRaises(HTTPException) as error:
                block_mock_in_production()
        self.assertEqual(error.exception.status_code, 404)
