import psycopg2
from psycopg2 import OperationalError
import os
from dotenv import load_dotenv

def test_connection():
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database connection details from environment variables
        db_config = {
            'host': os.getenv('DB_HOST', '44.211.203.69'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'vmail'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        
        print("Attempting to connect to database...")
        print(f"Connecting to: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        # Attempt to connect to the database
        conn = psycopg2.connect(**db_config)
        
        # Create a cursor
        cursor = conn.cursor()
        
        # Execute a simple query
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        
        print("\n✅ Connection successful!")
        print(f"PostgreSQL version: {db_version[0]}")
        
        # List all tables in the database
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        tables = cursor.fetchall()
        print("\nTables in the database:")
        for table in tables:
            print(f"- {table[0]}")
        
    except OperationalError as e:
        print(f"❌ Error connecting to the database: {e}")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    test_connection()
