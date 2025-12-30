# test_all_drivers.py
import os
from dotenv import load_dotenv
import pyodbc

load_dotenv()

def test_driver(driver_name):
    """Test a specific ODBC driver"""
    print(f"\nTesting: {driver_name}")
    
    server = os.getenv("DB_HOST", "localhost")
    database = os.getenv("DB_NAME", "Loyalty")
    username = os.getenv("DB_USER", "sa")
    password = os.getenv("DB_PASSWORD", "")
    
    # Connection string for this driver
    conn_str = (
        f'DRIVER={{{driver_name}}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
        'TrustServerCertificate=yes;'
        'Connection Timeout=5;'
    )
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Simple test query
        cursor.execute("SELECT 1 as test_value")
        result = cursor.fetchone()
        
        # Get server version
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        server_name = version.split('\t')[1] if '\t' in version else "SQL Server"
        
        conn.close()
        print(f"  ✅ SUCCESS - Connected to: {server_name.split()[0]}")
        return True
        
    except pyodbc.InterfaceError as e:
        print(f"  ❌ Interface Error: Driver not found or corrupted")
        return False
    except pyodbc.OperationalError as e:
        error_msg = str(e)
        if 'login' in error_msg.lower():
            print(f"  ❌ Authentication failed (wrong credentials)")
        elif 'server' in error_msg.lower():
            print(f"  ❌ Server not found (check host/port)")
        else:
            print(f"  ❌ Operational Error: {error_msg[:100]}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return False

# SQL Server drivers to test
sql_server_drivers = [
    "ODBC Driver 18 for SQL Server",  # Latest
    "ODBC Driver 17 for SQL Server",  # Recommended
    "ODBC Driver 13 for SQL Server",
    "ODBC Driver 11 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",  # Oldest
]

print("=" * 60)
print("Testing All SQL Server ODBC Drivers")
print("=" * 60)

working_drivers = []
for driver in sql_server_drivers:
    if test_driver(driver):
        working_drivers.append(driver)

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)

if working_drivers:
    print(f"✅ {len(working_drivers)} driver(s) work:")
    for i, driver in enumerate(working_drivers, 1):
        print(f"  {i}. {driver}")
    
    print(f"\n🎯 RECOMMENDED: Use '{working_drivers[0]}'")
    print(f"\nAdd to .env file:")
    print(f'DB_DRIVER={working_drivers[0].replace(" ", "+")}')
else:
    print("❌ No drivers worked. Check:")
    print("   1. SQL Server service is running")
    print("   2. SQL Server Authentication is enabled")
    print("   3. TCP/IP is enabled on port 1433")
    print("   4. Credentials are correct")
