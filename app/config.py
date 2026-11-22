from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Delicious Express AI"
    database_url: str = "sqlite:///./delicious_express.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.strip() and self.telegram_chat_id.strip())


settings = Settings()
