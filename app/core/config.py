from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./paylink.db"
    database_url_unpooled: str = ""
    jwt_secret: str = Field(min_length=32)
    frontend_url: str = "http://localhost:5173"
    cookie_secure: bool = True
    mailjet_api_key: str = ""
    mailjet_secret_key: str = ""
    mail_from: str = ""
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def use_psycopg(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def settings():
    return Settings()
