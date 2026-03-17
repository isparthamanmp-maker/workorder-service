import os
import sys
import logging
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Numeric, DateTime, TIMESTAMP, select, func
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sync_realisasi.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_HOST = os.getenv("DB_HOST", "10.10.1.7")
DB_USER = os.getenv("DB_USER", "sa")
DB_PASS = os.getenv("DB_PASSWORD", "spvsql")
DB_PORT = os.getenv("DB_PORT", "3306")

WO_DB_NAME = "work_order_system"
BUDGET_DB_NAME = "budget"

def get_engine(db_name):
    connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{db_name}?charset=utf8mb4"
    return create_engine(connection_string)

def sync_realisasi():
    logger.info("Starting Budget Realisasi Sync (v1.2 - removing status filter)...")
    
    wo_engine = get_engine(WO_DB_NAME)
    budget_engine = get_engine(BUDGET_DB_NAME)
    
    metadata_budget = MetaData()
    
    # 1. Define tables
    budget_final_realisasi = Table(
        'budget_final_realisasi', metadata_budget,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('budget_index', String(20), nullable=False),
        Column('refid', Integer, nullable=False),
        Column('refnum', String(100), nullable=False),
        Column('refvalue', Numeric(15, 2)),
        Column('created_at', TIMESTAMP, server_default=text('CURRENT_TIMESTAMP')),
        Column('created_by', String(100))
    )
    
    budget_final = Table(
        'budget_final', metadata_budget,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('budget_index', String(20), nullable=False),
        Column('total_realisasi', Numeric(15, 2), nullable=False, default=0)
    )

    try:
        metadata_budget.create_all(budget_engine)
        
        # 3. Fetch data from work_order_system
        # REMOVED: Status filter to include everything migrated
        # ENHANCED: CLEAN() logic to remove quotes, tabs, and spaces
        fetch_query = text("""
            SELECT 
                TRIM(REPLACE(REPLACE(REPLACE(REPLACE(wob.budget_index, '"', ''), "'", ""), '\t', ''), '\r\n', '')) as budget_index,
                wob.id as refid,
                wo.document_number as refnum,
                wob.cost_estimation as refvalue,
                wo.created_at,
                wo.submitted_by as created_by,
                wo.status
            FROM work_order_budgets wob
            JOIN work_orders wo ON wob.work_order_id = wo.id
        """)
        
        with wo_engine.connect() as wo_conn:
            logger.info("Fetching realisasi data from work_order_system (ALL statuses)...")
            realisasi_data = wo_conn.execute(fetch_query).fetchall()
            logger.info(f"Fetched {len(realisasi_data)} records total.")
            
            # Log status breakdown
            status_counts = {}
            for row in realisasi_data:
                status_counts[row.status] = status_counts.get(row.status, 0) + 1
            logger.info(f"Status breakdown: {status_counts}")
            
            # Log unique budget indexes fetched
            unique_fetched = set(row.budget_index for row in realisasi_data)
            logger.info(f"Unique budget indexes fetched: {sorted(list(unique_fetched))}")

        if not realisasi_data:
            logger.info("No records found to sync.")
            with budget_engine.begin() as budget_conn:
                budget_conn.execute(text("UPDATE budget_final SET total_realisasi = 0"))
            return

        # 4. Sync to budget.budget_final_realisasi
        with budget_engine.begin() as budget_conn:
            budget_conn.execute(text("TRUNCATE TABLE budget_final_realisasi"))
            logger.info("Truncated budget_final_realisasi.")
            
            insert_values = [
                {
                    'budget_index': row.budget_index,
                    'refid': row.refid,
                    'refnum': row.refnum,
                    'refvalue': row.refvalue,
                    'created_at': row.created_at,
                    'created_by': row.created_by
                }
                for row in realisasi_data
            ]
            
            budget_conn.execute(budget_final_realisasi.insert(), insert_values)
            logger.info(f"Inserted {len(insert_values)} records into budget_final_realisasi.")

        # 5. Recalculate total_realisasi in budget_final
        logger.info("Recalculating total_realisasi for budget_final...")
        with budget_engine.begin() as budget_conn:
            # Calculate totals per budget_index from the newly synced table
            calc_query = text("""
                SELECT budget_index, SUM(refvalue) as total 
                FROM budget_final_realisasi 
                GROUP BY budget_index
            """)
            
            totals = budget_conn.execute(calc_query).fetchall()
            
            # Reset all total_realisasi to 0 first
            budget_conn.execute(text("UPDATE budget_final SET total_realisasi = 0"))
            logger.info("Reset all total_realisasi in budget_final to 0.")
            
            # Update totals in budget_final
            affected_indexes = []
            for row in totals:
                # Use TRIM and REPLACE for robust matching in update too
                update_stmt = text("""
                    UPDATE budget_final 
                    SET total_realisasi = :total 
                    WHERE TRIM(REPLACE(REPLACE(REPLACE(REPLACE(budget_index, '"', ''), "'", ""), '\t', ''), '\r\n', '')) = :idx
                """)
                res = budget_conn.execute(update_stmt, {"total": row.total, "idx": row.budget_index.strip()})
                if res.rowcount > 0:
                    affected_indexes.append(row.budget_index)
                else:
                    logger.warning(f"Budget Index '{row.budget_index}' not found in budget_final table!")
                
            logger.info(f"Successfully updated total_realisasi for: {sorted(affected_indexes)}")

        logger.info("✅ Budget Realisasi Sync completed successfully.")

    except Exception as e:
        logger.error(f"Error during sync: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    sync_realisasi()
