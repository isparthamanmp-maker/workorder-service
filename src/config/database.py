from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    """Database configuration manager"""
    
    @staticmethod
    def get_connection_string() -> str:
        """Get connection string based on configured DB engine"""
        db_engine = os.getenv("DB_ENGINE", "sqlserver").lower()
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME", "microservice_db")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        
        # SQL Server
        if db_engine == "sqlserver":
            driver = os.getenv("DB_DRIVER", "ODBC+Driver+17+for+SQL+Server")
            port = f",{db_port}" if db_port else ""
            return f"mssql+pyodbc://{db_user}:{db_password}@{db_host}{port}/{db_name}?driver={driver}"
        
        # MySQL
        elif db_engine == "mysql":
            port = f":{db_port}" if db_port else ""
            # Use pymysql driver
            return f"mysql+pymysql://{db_user}:{db_password}@{db_host}{port}/{db_name}?charset=utf8mb4"
        
        # PostgreSQL
        elif db_engine == "postgresql":
            port = f":{db_port}" if db_port else ""
            return f"postgresql://{db_user}:{db_password}@{db_host}{port}/{db_name}"
        
        # Oracle
        elif db_engine == "oracle":
            port = f":{db_port}" if db_port else ":1521"
            service_name = os.getenv("DB_SERVICE_NAME", "ORCL")
            return f"oracle+cx_oracle://{db_user}:{db_password}@{db_host}{port}/?service_name={service_name}"
        
        else:
            raise ValueError(f"Unsupported database engine: {db_engine}")

class DatabaseManager:
    """Database connection manager"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.Base = declarative_base()
        self.metadata = MetaData()
        
    def init_db(self):
        """Initialize database connection"""
        connection_string = DatabaseConfig.get_connection_string()
        
        # Pool configuration
        pool_size = int(os.getenv("DB_POOL_SIZE", 10))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", 20))
        
        # Create engine with connection pooling
        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=os.getenv("DEBUG", "false").lower() == "true"
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Bind metadata
        self.Base.metadata = self.metadata
        self.metadata.bind = self.engine
        
    def get_db(self):
        """Get database session"""
        if self.SessionLocal is None:
            self.init_db()
        
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

# Global database manager instance
db_manager = DatabaseManager()
Base = db_manager.Base
get_db = db_manager.get_db