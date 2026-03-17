import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text, MetaData, Table, select, insert, Column, Integer, String, Numeric, DateTime as sqlalchemy_DateTime
from sqlalchemy.exc import IntegrityError

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
        logging.FileHandler('distribution.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def distribute():
    logger.info("Starting distribution process from wor_prod to main tables...")
    
    try:
        from src.config.database import db_manager
        db_manager.init_db()
        engine = db_manager.engine
        metadata = MetaData()
        
        # Reflect or define tables
        wor_prod = Table(
            'wor_prod', metadata,
            Column('id', Integer, primary_key=True),
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
            Column('scope_of_works', String(1000))
        )
        
        metadata.reflect(bind=engine, only=['work_orders', 'work_order_budgets', 'work_order_items'])
        
        work_orders = metadata.tables['work_orders']
        work_order_budgets = metadata.tables['work_order_budgets']
        work_order_items = metadata.tables['work_order_items']
        
        logger.info("Database tables reflected successfully.")
        
    except Exception as e:
        logger.error(f"Failed to initialize database or reflect tables: {e}")
        return

    try:
        with engine.begin() as conn:
            # 1. Fetch all data from wor_prod, excluding submitted_by = 'ENG'
            stmt = select(
                wor_prod.c.document_number,
                wor_prod.c.budget_index,
                wor_prod.c.rq_document_number,
                wor_prod.c.request_date,
                wor_prod.c.submitted_by,
                wor_prod.c.cost_estimation,
                wor_prod.c.rq_line_desc,
                wor_prod.c.quantity,
                wor_prod.c.unit_price,
                wor_prod.c.total_price,
                wor_prod.c.scope_of_works
            ).where(wor_prod.c.submitted_by != 'ENG').order_by(wor_prod.c.document_number)
            results = conn.execute(stmt).fetchall()
            
            logger.info(f"Fetched {len(results)} records from wor_prod (excluding 'ENG').")
            
            if not results:
                logger.info("No records to distribute.")
                return

            # Group results by document_number
            grouped_data = {}
            for row in results:
                doc_num = row.document_number
                if doc_num not in grouped_data:
                    grouped_data[doc_num] = []
                grouped_data[doc_num].append(row)

            inserted_count = 0
            skipped_count = 0
            
            for doc_num, items in grouped_data.items():
                # Header data from the first item in the group
                first_item = items[0]
                
                # Calculate total cost estimation for the header
                total_est = sum(float(item.total_price or 0) for item in items)

                header_data = {
                    'document_number': doc_num,
                    'request_date': first_item[3], # request_date (CreatedDateTime)
                    'start_date': first_item[3],   # Start Date from CreatedDateTime
                    'end_date': first_item[3],     # End Date from CreatedDateTime
                    'submitted_by': first_item[4], # submitted_by
                    'budget_index': first_item[1], # budget_index
                    'rq_document_number': first_item[2], # rq_document_number
                    'cost_estimation': total_est,
                    'scope_of_works': first_item[10], # scope_of_works
                    'status': 'Draft'
                }
                
                # 2. Insert into work_orders or get existing
                check_stmt = select(work_orders.c.id).where(work_orders.c.document_number == doc_num)
                existing_wo = conn.execute(check_stmt).fetchone()
                
                if existing_wo:
                    logger.info(f"Removing existing document_number for re-migration: {doc_num}")
                    # Delete items and budgets first
                    conn.execute(work_order_items.delete().where(work_order_items.c.work_order_id == existing_wo.id))
                    conn.execute(work_order_budgets.delete().where(work_order_budgets.c.work_order_id == existing_wo.id))
                    conn.execute(work_orders.delete().where(work_orders.c.id == existing_wo.id))
                
                try:
                    # Insert into work_orders
                    res = conn.execute(work_orders.insert().values(header_data))
                    work_order_id = res.inserted_primary_key[0]
                    
                    # 3. Handle multi-budget distribution
                    # Group items by budget_index for this work order
                    budget_groups = {}
                    for item in items:
                        b_idx = item[1] # budget_index
                        if b_idx not in budget_groups:
                            budget_groups[b_idx] = 0
                        budget_groups[b_idx] += float(item[9] or 0) # total_price

                    entry_order = 1
                    for b_idx, b_total in budget_groups.items():
                        budget_data = {
                            'work_order_id': work_order_id,
                            'budget_index': b_idx,
                            'budget_name': b_idx,
                            'cost_estimation': int(b_total),
                            'budget_remaining': int(b_total),
                            'under_over': 0.00,
                            'entry_order': entry_order,
                            'is_selected': 1
                        }
                        conn.execute(work_order_budgets.insert().values(budget_data))
                        entry_order += 1

                    # 4. Insert into work_order_items
                    item_count = 0
                    for item in items:
                        item_data = {
                            'work_order_id': work_order_id,
                            'description': item[6], # rq_line_desc
                            'quantity': item[7], # quantity
                            'unit_price': item[8], # unit_price
                            'total_price': item[9], # total_price
                            'item_order': item_count
                        }
                        conn.execute(work_order_items.insert().values(item_data))
                        item_count += 1
                    
                    inserted_count += 1
                    logger.info(f"Migrated document: {doc_num} (ID: {work_order_id}) with {len(items)} items and {len(budget_groups)} budgets.")
                    
                except IntegrityError as ie:
                    logger.warning(f"Integrity error for {doc_num}: {ie}")
                    skipped_count += 1
                    continue

            logger.info(f"Distribution Summary: {inserted_count} inserted, {skipped_count} skipped.")
            logger.info("✅ Distribution process completed.")

    except Exception as e:
        logger.error(f"An error occurred during distribution: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    distribute()
