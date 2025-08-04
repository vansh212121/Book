from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Bookly API"
    VERSION: str = "v1"
    DESCRIPTION: str = "A Rest API for Book management"

    API_V1_STR: str = "/api/v1"

    # --- Database & JWT Secrets ---
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    JWT_SECRET: str

    # Database Pool Settings
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_TIMEOUT: int = 30

    # --- Redis Configuration ---
    REDIS_URL: str

    #     # Mail Config
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    MAIL_DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
