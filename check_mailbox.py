import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor

def check_mailbox_table():
    try:
        # Connection parameters - update these with your actual credentials
        conn_params = {
            'host': '54.86.149.186',
            'port': '5432',
            'database': 'vmail',
            'user': 'postgres',
            'password': 'postgres'
        }
        
        print("🔍 Connecting to PostgreSQL database...")
        
        # Connect to the database
        with psycopg2.connect(**conn_params) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Get the count of mailboxes
                cur.execute("SELECT COUNT(*) AS count FROM mailbox")
                count = cur.fetchone()['count']
                print(f"✅ Successfully connected to database!")
                print(f"📊 Total mailboxes: {count:,}")
                
                # Get column names
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'mailbox' 
                    ORDER BY ordinal_position
                """)
                
                print("\n📋 Mailbox table structure:")
                print("-" * 80)
                for row in cur.fetchall():
                    print(f"{row['column_name']} ({row['data_type']})")
                
                # Get sample data (first 5 mailboxes)
                cur.execute("""
                    SELECT username, name, quota, created, active 
                    FROM mailbox 
                    ORDER BY created DESC 
                    LIMIT 5
                """)
                
                print("\n📧 Sample mailboxes (most recent 5):")
                print("-" * 80)
                for row in cur.fetchall():
                    print(f"📧 {row['username']}")
                    print(f"   👤 {row['name']}")
                    print(f"   💾 Quota: {row['quota']} bytes")
                    print(f"   🕒 Created: {row['created']}")
                    print(f"   ✅ Active: {'Yes' if row['active'] == 1 else 'No'}")
                    print("-" * 50)
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    check_mailbox_table()
