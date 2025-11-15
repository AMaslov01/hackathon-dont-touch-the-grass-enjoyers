"""
Script to update database structure with new businesses and employees tables
"""
import psycopg2
from config import Config
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def update_database():
    """Add new tables to existing database"""
    
    logger.info("Updating database structure...")
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Create businesses table
        logger.info("Creating businesses table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id SERIAL PRIMARY KEY,
                owner_id BIGINT NOT NULL REFERENCES users(user_id),
                business_name VARCHAR(255) NOT NULL,
                business_type TEXT,
                financial_situation TEXT,
                goals TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_id)
            )
        """)
        
        # Create employees table
        logger.info("Creating employees table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                invited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                UNIQUE(business_id, user_id)
            )
        """)
        
        # Create indexes
        logger.info("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_businesses_owner_id 
            ON businesses(owner_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_employees_business_id 
            ON employees(business_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_employees_user_id 
            ON employees(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_employees_status 
            ON employees(status)
        """)
        
        conn.commit()
        logger.info("✅ Database structure updated successfully!")
        
        # Verify tables
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('businesses', 'employees')
        """)
        tables = cursor.fetchall()
        
        print("\n✅ Created tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        print("\n📝 Next steps:")
        print("  1. Run migration script: python migrate_to_businesses.py")
        print("  2. Restart the bot")
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        print(f"\n❌ Database error: {e}")
        print("\n💡 Troubleshooting:")
        print("  - Check if PostgreSQL is running")
        print("  - Verify database credentials in config.env")
        print("  - Ensure users table exists")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")


if __name__ == '__main__':
    print("="*60)
    print("Database Structure Update Script")
    print("="*60)
    print()
    print("This script will add new tables:")
    print("  - businesses")
    print("  - employees")
    print()
    print("⚠️  Make sure you have a backup of your database!")
    print()
    
    try:
        Config.validate()
        print("✅ Configuration validated")
        print(f"   Host: {Config.DB_HOST}:{Config.DB_PORT}")
        print(f"   Database: {Config.DB_NAME}")
        print()
        
        response = input("Continue with update? (y/n): ")
        if response.lower() == 'y':
            update_database()
        else:
            print("Update cancelled")
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")

