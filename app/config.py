from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://anna_akulova:changeme@localhost:5432/anna_akulova"
    app_port: int = 8080
    secret_key: str = "changeme-secret-key"
    fine_per_day: int = 10
    loan_days: int = 14
    schema_name: str = "anna_akulova"


settings = Settings()
