from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CorteCero API"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/cortecero"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:3000"

    # Google Route Optimization API (E.2)
    # Autenticación vía Application Default Credentials / service account.
    # Dejar vacío para usar MockRouteOptimizationProvider (E.1, tests, dev).
    google_route_optimization_project_id: str = ""
    google_route_optimization_location: str = "global"
    google_route_optimization_timeout_seconds: float = 30.0

    # Coordenadas del depósito de salida (WGS-84).
    # Usadas por el proveedor de optimización como punto de inicio/fin de la ruta.
    # Default: Poligon Industrial Son Llaut 36, 07320 Santa Maria del Camí, Mallorca.
    # Coordenadas verificadas desde ficha de flota (hoja de cálculo operativa).
    route_optimization_depot_lat: float = 39.65779
    route_optimization_depot_lng: float = 2.79008

    # Cloudflare R2 — Proof of delivery photos (R8-POD-FOTO)
    # Dejar vacíos en dev/tests; se usará mock en los tests del bloque.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "cortecero-pod-photos"
    r2_public_url: str = ""  # e.g. https://pub-xxx.r2.dev

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
