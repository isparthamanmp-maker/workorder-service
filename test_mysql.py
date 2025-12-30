import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Get connection string from your configuration
from src.config.database import DatabaseConfig
connection_string = DatabaseConfig.get_connection_string()
print(f"Connection string: {connection_string}")

# Test connection
try:
    engine = create_engine(connection_string)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("✓ MySQL connection successful!")
        
        # Check database exists
        result = connection.execute(text("SELECT DATABASE()"))
        db_name = result.scalar()
        print(f"✓ Connected to database: {db_name}")
        
except Exception as e:
    print(f"✗ Connection failed: {e}")
