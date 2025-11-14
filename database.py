"""
Database models and operations using PostgreSQL
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from config import Config
from constants import TOKEN_CONFIG

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager"""
    
    def __init__(self):
        self.pool: Optional[SimpleConnectionPool] = None
    
    def connect(self):
        """Initialize database connection pool"""
        try:
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                # Disable connection timeout for long-running conversations
                connect_timeout=0,  # No timeout on initial connection
                keepalives=1,  # Enable TCP keepalive
                keepalives_idle=30,  # Start keepalive after 30 seconds
                keepalives_interval=10,  # Send keepalive every 10 seconds
                keepalives_count=5  # Close connection after 5 failed keepalives
            )
            logger.info("Database connection pool created successfully (no timeout)")
            self.create_tables()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_connection(self):
        """Get a connection from the pool with no timeouts"""
        if not self.pool:
            raise Exception("Database pool not initialized")
        conn = self.pool.getconn()
        
        # Configure session to prevent timeouts
        self.configure_session(conn)
        
        return conn
    
    def return_connection(self, conn):
        """Return connection to the pool"""
        if self.pool:
            self.pool.putconn(conn)
    
    def refresh_connection(self, conn):
        """Refresh a connection to prevent timeouts during long operations"""
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Failed to refresh connection: {e}")
            return False
    
    def close(self):
        """Close all database connections"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")
    
    def configure_session(self, conn):
        """Configure session settings to prevent timeouts"""
        try:
            with conn.cursor() as cursor:
                # Disable all timeouts for long-running conversations
                cursor.execute("SET statement_timeout = 0")
                cursor.execute("SET idle_in_transaction_session_timeout = 0")
                cursor.execute("SET lock_timeout = 0")
                conn.commit()
                logger.debug("Session timeout settings configured")
        except Exception as e:
            logger.warning(f"Failed to configure session settings: {e}")
    
    def create_tables(self):
        """Create necessary database tables"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        tokens INTEGER NOT NULL DEFAULT 0,
                        max_tokens INTEGER NOT NULL DEFAULT 100,
                        last_token_refresh TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        business_info TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Usage history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS usage_history (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(user_id),
                        prompt TEXT NOT NULL,
                        response TEXT NOT NULL,
                        tokens_used INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_history_user_id 
                    ON usage_history(user_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_history_created_at 
                    ON usage_history(created_at)
                """)
                
                conn.commit()
                logger.info("Database tables created successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create tables: {e}")
            raise
        finally:
            self.return_connection(conn)


class UserRepository:
    """Repository for user operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_user(self, user_id: int) -> Optional[dict]:
        """Get user by ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE user_id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        finally:
            self.db.return_connection(conn)
    
    def create_user(self, user_id: int, username: str = None, 
                   first_name: str = None, last_name: str = None) -> dict:
        """Create a new user"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, 
                                     tokens, max_tokens, last_token_refresh)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    user_id, username, first_name, last_name,
                    TOKEN_CONFIG['initial_tokens'],
                    TOKEN_CONFIG['max_tokens'],
                    datetime.now()
                ))
                conn.commit()
                result = cursor.fetchone()
                logger.info(f"Created new user: {user_id}")
                return dict(result)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create user {user_id}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def update_user_info(self, user_id: int, username: str = None,
                        first_name: str = None, last_name: str = None):
        """Update user information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET username = %s, first_name = %s, last_name = %s, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (username, first_name, last_name, user_id))
                conn.commit()
        finally:
            self.db.return_connection(conn)
    
    def get_or_create_user(self, user_id: int, username: str = None,
                          first_name: str = None, last_name: str = None) -> dict:
        """Get existing user or create a new one"""
        user = self.get_user(user_id)
        if user:
            # Update user info if changed
            if (username != user.get('username') or 
                first_name != user.get('first_name') or 
                last_name != user.get('last_name')):
                self.update_user_info(user_id, username, first_name, last_name)
                user = self.get_user(user_id)
            return user
        else:
            return self.create_user(user_id, username, first_name, last_name)
    
    def use_tokens(self, user_id: int, amount: int) -> bool:
        """Deduct tokens from user account"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET tokens = tokens - %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND tokens >= %s
                    RETURNING tokens
                """, (amount, user_id, amount))
                result = cursor.fetchone()
                conn.commit()
                return result is not None
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to use tokens for user {user_id}: {e}")
            return False
        finally:
            self.db.return_connection(conn)
    
    def refresh_tokens(self, user_id: int) -> dict:
        """Refresh user tokens if time has passed"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if refresh is needed
                cursor.execute("""
                    SELECT user_id, last_token_refresh, max_tokens
                    FROM users 
                    WHERE user_id = %s
                    AND last_token_refresh < %s
                """, (
                    user_id,
                    datetime.now() - timedelta(hours=TOKEN_CONFIG['refresh_interval_hours'])
                ))
                
                if cursor.fetchone():
                    # Refresh tokens
                    cursor.execute("""
                        UPDATE users 
                        SET tokens = max_tokens, 
                            last_token_refresh = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                        RETURNING *
                    """, (user_id,))
                    conn.commit()
                    result = cursor.fetchone()
                    logger.info(f"Refreshed tokens for user {user_id}")
                    return dict(result)
                else:
                    return self.get_user(user_id)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to refresh tokens for user {user_id}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def add_usage_history(self, user_id: int, prompt: str, 
                         response: str, tokens_used: int):
        """Add usage history record"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usage_history (user_id, prompt, response, tokens_used)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, prompt, response, tokens_used))
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to add usage history for user {user_id}: {e}")
        finally:
            self.db.return_connection(conn)
    
    def get_business_info(self, user_id: int) -> Optional[str]:
        """Get user's business information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT business_info FROM users WHERE user_id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result['business_info'] if result else None
        finally:
            self.db.return_connection(conn)
    
    def save_business_info(self, user_id: int, business_info: str) -> bool:
        """Save or update user's business information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET business_info = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (business_info, user_id))
                conn.commit()
                logger.info(f"Saved business info for user {user_id}")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save business info for user {user_id}: {e}")
            return False
        finally:
            self.db.return_connection(conn)


# Global database instance
db = Database()
user_repo = UserRepository(db)

