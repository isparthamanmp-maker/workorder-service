import os
import sys
import pyodbc
import logging
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy import text, Table, Column, Integer, String, DateTime as sqlalchemy_DateTime, Numeric, MetaData, create_engine
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
        logging.FileHandler('migration.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# SQL Server Source Configuration
SOURCE_CONFIG = {
    'host': '10.10.1.1\\PALDB01',
    'user': 'metabase_ro',
    'password': 'StrongPassword!',
    'database': 'PAL_LIVE',
    'driver': 'ODBC Driver 17 for SQL Server' # Defaulting to 17 as per implementation plan
}

TARGET_TABLE_NAME = 'wor_prod'

SOURCE_QUERY = """
select p.VendorRefNbr ,p.OrderNbr ,p2.RQReqNbr, p2.RQReqLineNbr,rl.UsrBudgetIndex ,rl.UsrReqOrderNbr ,rl.UsrReqLineNbr ,
rl2.OrderNbr RQNbr,r.UsrCreatedByDept ,e.Description deptname,r.CreatedByID , u.FullName ,u.Email ,u.Username ,
rl2.OrderQty,rl.EstUnitCost,
rl2.EstExtCost  ,p2.ExtCost ,rl2.EstExtCost -p2.ExtCost balance, rl2.Description	,r.Description rq_desc,r.CreatedDateTime
from POOrder p
inner join POLine p2 on p2.OrderNbr =p.OrderNbr and p2.CompanyID =p.CompanyID
left join RQRequisitionLine rl on rl.ReqNbr =p2.RQReqNbr and rl.LineNbr =p2.RQReqLineNbr  and rl.CompanyID =p2.CompanyID
left join RQRequestLine rl2 on rl2.OrderNbr =rl.UsrReqOrderNbr and rl2.LineNbr =rl.UsrReqLineNbr and rl2.CompanyID =rl.CompanyID
left join RQRequest r on r.CompanyID =rl2.CompanyID and r.OrderNbr =rl2.OrderNbr
inner join EPDepartment e on e.CompanyID =r.CompanyID and e.DepartmentID =r.UsrCreatedByDept
inner join Users u on u.CompanyID =r.CompanyID  and u.PKID =r.CreatedByID
where p.companyid=3
and year(p.OrderDate)=2026	
and rl.UsrBudgetIndex like '%26-%'
and e.Description not in ('ENGINEERING', 'ENGINEER', 'ENG')
order by p.VendorRefNbr
"""

def get_source_connection():
    conn_str = (
        f"DRIVER={{{SOURCE_CONFIG['driver']}}};"
        f"SERVER={SOURCE_CONFIG['host']};"
        f"DATABASE={SOURCE_CONFIG['database']};"
        f"UID={SOURCE_CONFIG['user']};"
        f"PWD={SOURCE_CONFIG['password']};"
        "TrustServerCertificate=yes;"
    )
    try:
        return pyodbc.connect(conn_str)
    except Exception as e:
        logger.error(f"Failed to connect to Source SQL Server: {e}")
        # Try alternate driver if 17 fails
        logger.info("Attempting with 'SQL Server' legacy driver...")
        conn_str_legacy = conn_str.replace(SOURCE_CONFIG['driver'], "SQL Server")
        return pyodbc.connect(conn_str_legacy)

def migrate():
    logger.info("Starting migration process...")
    
    # 1. Initialize MySQL Target Connection via existing db_manager
    try:
        from src.config.database import db_manager
        db_manager.init_db()
        target_engine = db_manager.engine
        logger.info("Target connection initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize target connection: {e}")
        return

    # 2. Ensure target table exists
    metadata = MetaData()
    wor_prod = Table(
        TARGET_TABLE_NAME, metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('document_number', String(100)),
        Column('budget_index', String(100)),
        Column('rq_document_number', String(100)),
        Column('request_date', sqlalchemy_DateTime),
        Column('submitted_by', String(255)),
        Column('cost_estimation', Numeric(18, 2)),
        Column('rq_line_desc', String(500)),
        Column('quantity', Numeric(18, 2)),
        Column('unit_price', Numeric(18, 2)),
        Column('total_price', Numeric(18, 2)),
        Column('scope_of_works', String(1000)),
        Column('migrated_at', sqlalchemy_DateTime, server_default=text('CURRENT_TIMESTAMP'))
    )
    
    try:
        wor_prod.drop(target_engine, checkfirst=True)
        metadata.create_all(target_engine)
        logger.info(f"Verified/Created target table: {TARGET_TABLE_NAME}")
    except Exception as e:
        logger.error(f"Failed to create target table: {e}")
        return

    # 3. Connect to Source and Fetch Data
    source_conn = None
    try:
        source_conn = get_source_connection()
        cursor = source_conn.cursor()
        
        logger.info("Fetching data from SQL Server...")
        cursor.execute(SOURCE_QUERY)
        
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
        
        logger.info(f"Fetched {len(data)} rows from source.")
        
        if not data:
            logger.info("No data found to migrate.")
            return

        # 4. Data Transformation
        logger.info("Applying data conversions...")
        transformed_data = []
        for row in data:
            # Map source columns to target columns
            item = {
                'document_number': row.get('VendorRefNbr'),
                'budget_index': row.get('UsrBudgetIndex'),
                'rq_document_number': row.get('UsrReqOrderNbr'),
                'request_date': row.get('CreatedDateTime'),
                'submitted_by': row.get('deptname'),
                'cost_estimation': row.get('EstExtCost'), # User said cost_estimation = EstExtCost in previous context, but now we have items.
                'rq_line_desc': row.get('Description'),
                'quantity': row.get('OrderQty'),
                'unit_price': row.get('EstUnitCost'),
                'total_price': row.get('balance'), # Will be overwritten below
                'scope_of_works': row.get('rq_desc')
            }

            # User corrected total_price in mid-convo
            qty = item['quantity'] or 0
            price = item['unit_price'] or 0
            item['total_price'] = float(qty) * float(price)

            # Convert 'Engineering' variants to 'ENG' in submitted_by
            sub_by = item.get('submitted_by')
            if sub_by and sub_by.upper() in ['ENGINEERING', 'ENGINEER', 'ENG']:
                item['submitted_by'] = 'ENG'
            
            # Convert 'ENGINEERING' or 'ENGINEER' variants to 'ENG' in document_number
            doc_num = item.get('document_number')
            if doc_num:
                # Replace ENGINEERING first (longer match) then ENGINEER
                new_doc_num = doc_num.replace('ENGINEERING', 'ENG').replace('Engineering', 'ENG')
                new_doc_num = new_doc_num.replace('ENGINEER', 'ENG').replace('Engineer', 'ENG')
                new_doc_num = new_doc_num.replace('WOR.ENG', 'WOR/ENG')
                item['document_number'] = new_doc_num
            
            transformed_data.append(item)

        # 5. Insert into Target
        logger.info(f"Truncating and inserting data into {TARGET_TABLE_NAME}...")
        
        with target_engine.begin() as conn:
            # Truncate the table first
            conn.execute(text(f"TRUNCATE TABLE {TARGET_TABLE_NAME}"))
            logger.info(f"Table {TARGET_TABLE_NAME} truncated.")
            
            # Insert the new data
            conn.execute(wor_prod.insert(), transformed_data)
            
        logger.info("Migration completed successfully.")

    except Exception as e:
        logger.error(f"An error occurred during migration: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if source_conn:
            source_conn.close()

if __name__ == "__main__":
    migrate()
