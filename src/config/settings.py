from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_name: str = "MicroserviceDB"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    db_engine: str = "sqlserver"
    db_host: str = "localhost"
    db_port: Optional[int] = None
    db_name: str = "microservice_db"
    db_user: str = ""
    db_password: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Database specific
    db_driver: Optional[str] = None
    db_service_name: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = ""

settings = Settings()