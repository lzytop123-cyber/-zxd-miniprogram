from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    base_url: str = "http://localhost:8000"
    # 小程序/商户审核中：生产环境仍允许 dev 登录与 mock 支付（未配置 WX 凭证时）
    pre_wechat_launch: bool = False

    database_url: str = "sqlite:///./zxd_study.db"
    redis_url: str = "redis://localhost:6379/0"

    wx_appid: str = ""
    wx_app_secret: str = ""
    wx_pay_mchid: str = ""
    wx_pay_serial_no: str = ""
    wx_pay_api_v3_key: str = ""
    wx_pay_cert_path: str = "./certs/apiclient_cert.pem"
    wx_pay_key_path: str = "./certs/apiclient_key.pem"

    ttlock_client_id: str = ""
    ttlock_client_secret: str = ""
    ttlock_username: str = ""
    ttlock_password: str = ""

    yunlaoban_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("YUNLAOBAN_CLIENT_ID", "MEITUAN_CLIENT_ID"),
    )
    yunlaoban_secret: str = Field(
        default="",
        validation_alias=AliasChoices("YUNLAOBAN_SECRET", "MEITUAN_SECRET"),
    )
    yunlaoban_shop_id: str = Field(
        default="",
        validation_alias=AliasChoices("YUNLAOBAN_SHOP_ID", "MEITUAN_SHOP_ID"),
    )
    yunlaoban_platform: int = Field(
        default=1,
        validation_alias=AliasChoices("YUNLAOBAN_PLATFORM", "MEITUAN_PLATFORM"),
    )
    yunlaoban_base_url: str = Field(
        default="https://openapi.yunlaoban.vip",
        validation_alias=AliasChoices("YUNLAOBAN_BASE_URL", "MEITUAN_BASE_URL"),
    )
    yunlaoban_timeout_ms: int = Field(
        default=20000,
        validation_alias=AliasChoices("YUNLAOBAN_TIMEOUT", "MEITUAN_TIMEOUT"),
    )
    coupon_provider: str = Field(
        default="auto",
        validation_alias=AliasChoices("COUPON_PROVIDER"),
    )

    admin_username: str = "admin"
    admin_password: str = "admin123"

    jwt_expire_days: int = 7

    @property
    def wx_login_configured(self) -> bool:
        appid = (self.wx_appid or "").strip()
        return bool(appid) and not appid.startswith("your_") and "XXXX" not in appid

    @property
    def wx_pay_configured(self) -> bool:
        return bool((self.wx_pay_mchid or "").strip())

    @computed_field
    @property
    def yunlaoban_timeout_sec(self) -> float:
        return self.yunlaoban_timeout_ms / 1000.0


settings = Settings()
