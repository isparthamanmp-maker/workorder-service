
from src.config.database import db_manager
from sqlalchemy import text

def migrate():
    db_manager.init_db()
    with db_manager.engine.connect() as conn:
        print("Checking for columns in work_orders_history...")
        result = conn.execute(text("SHOW COLUMNS FROM work_orders_history"))
        columns = [row[0] for row in result]
        
        if 'remarks' not in columns:
            print("Adding remarks column to work_orders_history...")
            conn.execute(text("ALTER TABLE work_orders_history ADD COLUMN remarks TEXT NULL"))
            print("remarks column added successfully.")
        else:
            print("remarks column already exists in work_orders_history.")
            
        conn.commit()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
