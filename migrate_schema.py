
from src.config.database import db_manager
from sqlalchemy import text

def migrate():
    db_manager.init_db()
    with db_manager.engine.connect() as conn:
        print("Checking for columns in work_order_files...")
        result = conn.execute(text("SHOW COLUMNS FROM work_order_files"))
        columns = [row[0] for row in result]
        
        if 'refid' not in columns:
            print("Adding refid column...")
            conn.execute(text("ALTER TABLE work_order_files ADD COLUMN refid INT NOT NULL DEFAULT 0"))
        else:
            print("refid column already exists.")
            
        if 'revno' not in columns:
            print("Adding revno column...")
            conn.execute(text("ALTER TABLE work_order_files ADD COLUMN revno INT NOT NULL DEFAULT 0"))
        else:
            print("revno column already exists.")
            
        conn.commit()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
