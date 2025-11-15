"""
Migration script to move business_info from users table to businesses table
Run this after updating the database structure
"""
import logging
import json
from database import db, user_repo, business_repo

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def migrate_business_info():
    """Migrate business_info from users table to businesses table"""
    
    logger.info("Starting migration...")
    
    # Connect to database
    db.connect()
    
    try:
        # Get connection
        conn = db.get_connection()
        
        try:
            with conn.cursor() as cursor:
                # Check if business_info column still exists in users table
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='business_info'
                """)
                
                has_business_info_column = cursor.fetchone() is not None
                
                if not has_business_info_column:
                    logger.info("Column 'business_info' not found in users table. Migration not needed or already completed.")
                    return
                
                # Get all users with business_info
                cursor.execute("""
                    SELECT user_id, business_info 
                    FROM users 
                    WHERE business_info IS NOT NULL AND business_info != ''
                """)
                
                users_with_business = cursor.fetchall()
                
                if not users_with_business:
                    logger.info("No users with business_info found. Nothing to migrate.")
                    return
                
                logger.info(f"Found {len(users_with_business)} users with business info to migrate")
                
                migrated = 0
                errors = 0
                
                for user_id, business_info_json in users_with_business:
                    try:
                        # Parse business_info JSON
                        business_info = json.loads(business_info_json)
                        
                        # Extract fields
                        business_type = business_info.get('business_type', '')
                        financial_situation = business_info.get('financial_situation', '')
                        goals = business_info.get('goals', '')
                        
                        # Generate business name (if not exists in old data)
                        # Use first 50 chars of business_type as name
                        if business_type:
                            business_name = business_type[:50] if len(business_type) > 50 else business_type
                        else:
                            business_name = f"Бизнес пользователя {user_id}"
                        
                        # Check if business already exists for this owner
                        existing = business_repo.get_business(user_id)
                        
                        if existing:
                            logger.info(f"Business already exists for user {user_id}, skipping")
                            continue
                        
                        # Create business
                        business_repo.create_business(
                            owner_id=user_id,
                            business_name=business_name,
                            business_type=business_type,
                            financial_situation=financial_situation,
                            goals=goals
                        )
                        
                        migrated += 1
                        logger.info(f"Migrated business for user {user_id}")
                        
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse business_info for user {user_id}")
                        errors += 1
                    except Exception as e:
                        logger.error(f"Failed to migrate business for user {user_id}: {e}")
                        errors += 1
                
                logger.info(f"Migration completed: {migrated} migrated, {errors} errors")
                
                # Ask user if they want to drop the business_info column
                print("\n" + "="*60)
                print("Migration Summary:")
                print(f"  Successfully migrated: {migrated}")
                print(f"  Errors: {errors}")
                print("="*60)
                print("\nThe 'business_info' column in 'users' table is no longer needed.")
                print("You can remove it manually with:")
                print("  ALTER TABLE users DROP COLUMN business_info;")
                print("\nOr keep it for backup purposes.")
                
        finally:
            db.return_connection(conn)
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == '__main__':
    print("="*60)
    print("Business Info Migration Script")
    print("="*60)
    print()
    print("This script will migrate business_info from users table")
    print("to the new businesses table.")
    print()
    
    response = input("Continue with migration? (y/n): ")
    if response.lower() == 'y':
        migrate_business_info()
        print("\n✅ Migration completed!")
    else:
        print("Migration cancelled")

