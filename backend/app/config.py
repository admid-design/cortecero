from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CorteCero API"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cortecero"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:3000"

    # Google Route Optimization API (E.2)
    # Autenticación vía Application Default Credentials / service account.
    # Dejar vacío para usar MockRouteOptimizationProvider (E.1, tests, dev).
    google_route_optimization_project_id: str = ""
    google_route_optimization_location: str = "global"

    # Coordenadas del depósito de salida (WGS-84).
    # Usadas por el proveedor de optimización como punto de inicio/fin de la ruta.
    # Default: Palma de Mallorca centro (POC).
    route_optimization_depot_lat: float = 39.5696
    route_optimization_depot_lng: float = 2.6502

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
