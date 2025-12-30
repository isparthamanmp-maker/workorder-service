# create_tables_fixed.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment FIRST
load_dotenv()

print("=" * 60)
print("CREATING TABLES FROM MODELS")
print("=" * 60)

try:
    # 1. Initialize database manager FIRST
    from src.config.database import db_manager
    print("Initializing database connection...")
    db_manager.init_db()
    
    # 2. Now import Base
    from src.models.base import Base
    
    # 3. CRITICAL: Import ALL your model classes
    # This ensures they're registered with Base.metadata
    print("Importing models...")
    
    # Method 1: Import each model explicitly
    from src.models.base import User, Product, Order
    print(f"Imported models: User, Product, Order")
    
    # Method 2: Or import the entire module
    import src.models.base as models
    print(f"Models module loaded: {models.__name__}")
    
    # 4. Check what tables SQLAlchemy knows about
    print(f"\nTables registered with Base.metadata:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
    
    if not Base.metadata.tables:
        print("❌ No tables found in metadata!")
        print("Models might not be properly defined or imported.")
        sys.exit(1)
    
    # 5. Create tables
    print(f"\nCreating {len(Base.metadata.tables)} table(s)...")
    Base.metadata.create_all(bind=db_manager.engine)
    
    # 6. Verify in database
    print("\nVerifying in database...")
    with db_manager.engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        db_tables = [row[0] for row in result]
        
        if db_tables:
            print("✅ Tables in database:")
            for table in db_tables:
                print(f"  - {table}")
        else:
            print("❌ No tables found in database!")
            
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Check your project structure and imports.")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
