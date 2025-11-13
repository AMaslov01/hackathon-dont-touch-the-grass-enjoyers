"""
Quick database setup script
Run this to create the database and tables
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import Config

def setup_database():
    """Create database and tables"""
    print("🔧 Setting up database...")
    
    try:
        # Connect to PostgreSQL server (not specific database)
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database='postgres'  # Connect to default database first
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (Config.DB_NAME,)
        )
        
        if not cursor.fetchone():
            print(f"Creating database: {Config.DB_NAME}")
            cursor.execute(f"CREATE DATABASE {Config.DB_NAME}")
            print(f"✅ Database '{Config.DB_NAME}' created")
        else:
            print(f"ℹ️  Database '{Config.DB_NAME}' already exists")
        
        cursor.close()
        conn.close()
        
        # Now connect to our database and create tables
        print("\n📊 Creating tables...")
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        
        # Read and execute schema file
        with open('schema.sql', 'r', encoding='utf-8') as f:
            schema = f.read()
        
        cursor = conn.cursor()
        cursor.execute(schema)
        conn.commit()
        
        print("✅ Tables created successfully")
        
        # Verify tables
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()
        print("\n📋 Created tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        print("\n✨ Database setup complete!")
        print(f"\nConnection URL: {Config.get_database_url()}")
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection error: {e}")
        print("\n💡 Make sure PostgreSQL is running:")
        print("   sudo systemctl start postgresql")
        print("\n💡 Or check your credentials in config.env")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("=" * 50)
    print("Database Setup Script")
    print("=" * 50)
    print()
    
    try:
        Config.validate()
        print("✅ Configuration validated")
        print(f"   Host: {Config.DB_HOST}:{Config.DB_PORT}")
        print(f"   Database: {Config.DB_NAME}")
        print(f"   User: {Config.DB_USER}")
        print()
        
        response = input("Continue with database setup? (y/n): ")
        if response.lower() == 'y':
            setup_database()
        else:
            print("Setup cancelled")
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")

