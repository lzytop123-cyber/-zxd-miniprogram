import logging

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_WEAK_SECRETS = {"", "change-me", "secret", "changeme"}
_WEAK_PASSWORDS = {"", "admin123", "admin", "123456", "password"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    base_url: str = "http://localhost:8000"
    # 小程序/商户审核中：生产环境仍允许 dev 登录与 mock 支付（未配置 WX 凭证时）
    pre_wechat_launch: bool = False
    # 小程序「学习助手」Tab：审核期可置 false 隐藏，通过后改 true 并重启后端（不必重传小程序）
    feature_study_assistant: bool = Field(
        default=True,
        validation_alias=AliasChoices("FEATURE_STUDY_ASSISTANT", "feature_study_assistant"),
    )
    # 允许的跨域来源：逗号分隔；为 "*" 时开发环境放开（生产应配置白名单）
    cors_origins: str = "*"

    database_url: str = "sqlite:///./zxd_study.db"
    redis_url: str = "redis://localhost:6379/0"

    wx_appid: str = ""
    wx_app_secret: str = ""
    wx_pay_mchid: str = ""
    wx_pay_serial_no: str = ""
    wx_pay_api_v3_key: str = ""
    wx_pay_cert_path: str = "./certs/apiclient_cert.pem"
    wx_pay_key_path: str = "./certs/apiclient_key.pem"
    # 平台公钥模式（响应头为 PUB_KEY_ID_... 时必填）
    wx_pay_public_key_path: str = "./cert/pub_key.pem"
    wx_pay_public_key_id: str = ""
    # 期限卡到期订阅消息模板 ID（小程序后台申请后填入）
    wx_subscribe_card_expire_tmpl_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "WX_SUBSCRIBE_CARD_EXPIRE_TMPL_ID",
            "wx_subscribe_card_expire_tmpl_id",
        ),
    )

    ttlock_client_id: str = ""
    ttlock_client_secret: str = ""
    ttlock_username: str = ""
    ttlock_password: str = ""
    # 需 WiFi 网关；纯蓝牙锁保持 false
    ttlock_remote_unlock_enabled: bool = False

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

    douyin_client_key: str = Field(
        default="",
        validation_alias=AliasChoices("DOUYIN_CLIENT_KEY", "DOUYIN_APP_ID"),
    )
    douyin_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("DOUYIN_CLIENT_SECRET", "DOUYIN_APP_SECRET"),
    )
    douyin_poi_id: str = Field(
        default="",
        validation_alias=AliasChoices("DOUYIN_POI_ID"),
    )
    douyin_coupon_provider: str = Field(
        default="auto",
        validation_alias=AliasChoices("DOUYIN_COUPON_PROVIDER"),
    )

    admin_username: str = "admin"
    admin_password: str = "admin123"

    jwt_expire_days: int = 7

    health_alert_webhook: str = ""

    # DeepSeek AI 学习助手（OpenAI 兼容接口）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_embedding_model: str = "deepseek-embedding"
    deepseek_timeout_sec: float = 30.0

    # AI 知识库 RAG（ChromaDB + DeepSeek Embedding）
    knowledge_rag_enabled: bool = True
    knowledge_rag_top_k: int = 5
    knowledge_chunk_size: int = 600
    knowledge_chunk_overlap: int = 80

    @property
    def assistant_configured(self) -> bool:
        key = (self.deepseek_api_key or "").strip()
        return bool(key) and not key.startswith("your_") and "XXXX" not in key

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

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def validate_for_production(self) -> None:
        """生产环境强制安全基线，弱默认值直接拒绝启动。"""
        if not self.is_production:
            return
        errors: list[str] = []
        if (self.secret_key or "").strip().lower() in _WEAK_SECRETS or len(self.secret_key) < 16:
            errors.append("SECRET_KEY 过弱，请设置 ≥16 位的随机强密钥")
        if (self.admin_password or "").strip().lower() in _WEAK_PASSWORDS:
            errors.append("ADMIN_PASSWORD 为弱默认值，请设置强密码")
        if self.cors_origin_list == ["*"]:
            errors.append('CORS_ORIGINS 不能为 "*"（携带凭证时浏览器也会拒绝），请配置域名白名单')
        if errors:
            raise RuntimeError("生产环境配置校验失败：\n- " + "\n- ".join(errors))
        if self.pre_wechat_launch and not self.wx_pay_configured:
            logger.warning(
                "PRE_WECHAT_LAUNCH=true 且未配置微信支付：生产环境仍允许 dev 登录与 mock 支付，"
                "审核通过后请置为 false。"
            )


settings = Settings()
