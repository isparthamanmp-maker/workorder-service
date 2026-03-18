# migration/add_remarks_to_files.py
import sys
import os
from sqlalchemy import text

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import db_manager

def migrate():
    print("Starting migration: Add remarks column to work_order_files table")
    db_manager.init_db()
    
    with db_manager.engine.connect() as connection:
        # Check if column exists first (optional but safer)
        # For MySQL:
        check_sql = text("SHOW COLUMNS FROM work_order_files LIKE 'remarks'")
        result = connection.execute(check_sql).fetchone()
        
        if not result:
            print("Adding 'remarks' column...")
            alter_sql = text("ALTER TABLE work_order_files ADD COLUMN remarks TEXT NULL")
            connection.execute(alter_sql)
            connection.commit()
            print("Successfully added 'remarks' column.")
        else:
            print("'remarks' column already exists.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
