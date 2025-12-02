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
                        workers_info TEXT,
                        executors_info TEXT,
                        completed_tasks INTEGER DEFAULT 0,
                        abandonments_count INTEGER DEFAULT 0,
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

                # Businesses table
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

                # Employees table (invitations and accepted employees)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS employees (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                        user_id BIGINT NOT NULL REFERENCES users(user_id),
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        rating INTEGER NOT NULL DEFAULT 500,
                        invited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        responded_at TIMESTAMP,
                        UNIQUE(business_id, user_id)
                    )
                """)

                # Tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                        title VARCHAR(500) NOT NULL,
                        description TEXT,
                        assigned_to BIGINT REFERENCES users(user_id),
                        created_by BIGINT NOT NULL REFERENCES users(user_id),
                        status VARCHAR(20) NOT NULL DEFAULT 'available',
                        ai_recommended_employee BIGINT REFERENCES users(user_id),
                        abandoned_by BIGINT REFERENCES users(user_id),
                        abandoned_at TIMESTAMP,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        assigned_at TIMESTAMP,
                        completed_at TIMESTAMP
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

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_business_id 
                    ON tasks(business_id)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to 
                    ON tasks(assigned_to)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_status 
                    ON tasks(status)
                """)

                
                # Migration: Add rating column to employees table if it doesn't exist
                cursor.execute("""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'employees' AND column_name = 'rating'
                        ) THEN
                            ALTER TABLE employees ADD COLUMN rating INTEGER NOT NULL DEFAULT 500;
                            RAISE NOTICE 'Added rating column to employees table';
                        END IF;
                    END $$;
                """)
                
                conn.commit()
                logger.info("Database tables created successfully")
                
                # Run migrations for existing tables
                self.run_migrations(conn)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create tables: {e}")
            raise
        finally:
            self.return_connection(conn)
    
    def run_migrations(self, conn):
        """Run database migrations for schema updates"""
        try:
            with conn.cursor() as cursor:
                # Migration 1: Add abandoned_by and abandoned_at columns to tasks table
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='tasks' AND column_name='abandoned_by'
                        ) THEN
                            ALTER TABLE tasks ADD COLUMN abandoned_by BIGINT REFERENCES users(user_id);
                            ALTER TABLE tasks ADD COLUMN abandoned_at TIMESTAMP;
                            RAISE NOTICE 'Added abandoned_by and abandoned_at columns to tasks table';
                        END IF;
                    END $$;
                """)
                
                # Migration 2: Add completed_tasks and abandonments_count columns to users table
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='users' AND column_name='completed_tasks'
                        ) THEN
                            ALTER TABLE users ADD COLUMN completed_tasks INTEGER DEFAULT 0;
                            RAISE NOTICE 'Added completed_tasks column to users table';
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='users' AND column_name='abandonments_count'
                        ) THEN
                            ALTER TABLE users ADD COLUMN abandonments_count INTEGER DEFAULT 0;
                            RAISE NOTICE 'Added abandonments_count column to users table';
                        END IF;
                    END $$;
                """)
                
                conn.commit()
                logger.info("Database migrations completed successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to run migrations: {e}")
            raise


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
    
    def get_usage_history(self, user_id: int, limit: int = None) -> list:
        """Get usage history for a user"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if limit:
                    cursor.execute("""
                        SELECT prompt, response, tokens_used, created_at
                        FROM usage_history
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (user_id, limit))
                else:
                    cursor.execute("""
                        SELECT prompt, response, tokens_used, created_at
                        FROM usage_history
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                    """, (user_id,))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get usage history for user {user_id}: {e}")
            return []
        finally:
            self.db.return_connection(conn)


    def get_workers_info(self, user_id: int) -> Optional[str]:
        """Get user's workers search information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT workers_info FROM users WHERE user_id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result['workers_info'] if result else None
        finally:
            self.db.return_connection(conn)

    def save_workers_info(self, user_id: int, workers_info: str) -> bool:
        """Save or update user's workers search information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET workers_info = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (workers_info, user_id))
                conn.commit()
                logger.info(f"Saved workers info for user {user_id}")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save workers info for user {user_id}: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def get_executors_info(self, user_id: int) -> Optional[str]:
        """Get user's executors search information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT executors_info FROM users WHERE user_id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result['executors_info'] if result else None
        finally:
            self.db.return_connection(conn)

    def save_executors_info(self, user_id: int, executors_info: str) -> bool:
        """Save or update user's executors search information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET executors_info = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (executors_info, user_id))
                conn.commit()
                logger.info(f"Saved executors info for user {user_id}")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save executors info for user {user_id}: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def get_all_users_with_business_info(self, exclude_user_id: int = None) -> list:
        """Get all users who have business info (from businesses table)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if exclude_user_id:
                    cursor.execute("""
                        SELECT u.user_id, u.username, u.first_name, u.last_name, 
                               u.workers_info, u.executors_info,
                               b.business_name, b.business_type, 
                               b.financial_situation, b.goals
                        FROM users u
                        JOIN businesses b ON u.user_id = b.owner_id
                        WHERE u.user_id != %s
                    """, (exclude_user_id,))
                else:
                    cursor.execute("""
                        SELECT u.user_id, u.username, u.first_name, u.last_name,
                               u.workers_info, u.executors_info,
                               b.business_name, b.business_type, 
                               b.financial_situation, b.goals
                        FROM users u
                        JOIN businesses b ON u.user_id = b.owner_id
                    """)

                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get users with business info: {e}")
            return []
        finally:
            self.db.return_connection(conn)


class BusinessRepository:
    """Repository for business and employee operations"""

    def __init__(self, db: Database):
        self.db = db

    def get_business(self, owner_id: int) -> Optional[dict]:
        """Get business by owner ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM businesses WHERE owner_id = %s",
                    (owner_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        finally:
            self.db.return_connection(conn)

    def get_business_by_id(self, business_id: int) -> Optional[dict]:
        """Get business by business ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM businesses WHERE id = %s",
                    (business_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        finally:
            self.db.return_connection(conn)

    def create_business(self, owner_id: int, business_name: str,
                       business_type: str = None, financial_situation: str = None,
                       goals: str = None) -> dict:
        """Create a new business"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO businesses (owner_id, business_name, business_type, 
                                          financial_situation, goals)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                """, (owner_id, business_name, business_type, financial_situation, goals))
                conn.commit()
                result = cursor.fetchone()
                logger.info(f"Created new business for owner {owner_id}: {business_name}")
                return dict(result)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create business for owner {owner_id}: {e}")
            raise
        finally:
            self.db.return_connection(conn)

    def update_business(self, owner_id: int, business_name: str = None,
                       business_type: str = None, financial_situation: str = None,
                       goals: str = None) -> bool:
        """Update business information"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE businesses 
                    SET business_name = COALESCE(%s, business_name),
                        business_type = COALESCE(%s, business_type),
                        financial_situation = COALESCE(%s, financial_situation),
                        goals = COALESCE(%s, goals),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE owner_id = %s
                """, (business_name, business_type, financial_situation, goals, owner_id))
                conn.commit()
                logger.info(f"Updated business for owner {owner_id}")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update business for owner {owner_id}: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def save_or_update_business(self, owner_id: int, business_name: str,
                               business_type: str = None, financial_situation: str = None,
                               goals: str = None) -> dict:
        """Create or update business"""
        existing = self.get_business(owner_id)
        if existing:
            self.update_business(owner_id, business_name, business_type,
                               financial_situation, goals)
            return self.get_business(owner_id)
        else:
            return self.create_business(owner_id, business_name, business_type,
                                       financial_situation, goals)

    def get_user_by_username(self, username: str) -> Optional[int]:
        """Get user_id by username"""
        if not username:
            return None
        # Remove @ if present
        username = username.lstrip('@')

        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT user_id FROM users WHERE username = %s",
                    (username,)
                )
                result = cursor.fetchone()
                return result['user_id'] if result else None
        finally:
            self.db.return_connection(conn)

    def invite_employee(self, business_id: int, user_id: int) -> bool:
        """Invite a user to be an employee"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO employees (business_id, user_id, status)
                    VALUES (%s, %s, 'pending')
                    ON CONFLICT (business_id, user_id) DO NOTHING
                    RETURNING id
                """, (business_id, user_id))
                result = cursor.fetchone()
                conn.commit()
                if result:
                    logger.info(f"Invited user {user_id} to business {business_id}")
                    return True
                else:
                    logger.warning(f"Invitation already exists for user {user_id} to business {business_id}")
                    return False
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to invite employee: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def get_pending_invitations(self, user_id: int) -> list:
        """Get all pending invitations for a user"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT e.id, e.business_id, e.invited_at,
                           b.business_name, b.owner_id,
                           u.username as owner_username, u.first_name as owner_first_name
                    FROM employees e
                    JOIN businesses b ON e.business_id = b.id
                    JOIN users u ON b.owner_id = u.user_id
                    WHERE e.user_id = %s AND e.status = 'pending'
                    ORDER BY e.invited_at DESC
                """, (user_id,))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get pending invitations for user {user_id}: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def respond_to_invitation(self, invitation_id: int, accept: bool) -> bool:
        """Accept or reject an invitation"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                new_status = 'accepted' if accept else 'rejected'
                cursor.execute("""
                    UPDATE employees 
                    SET status = %s, responded_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'pending'
                    RETURNING id
                """, (new_status, invitation_id))
                result = cursor.fetchone()
                conn.commit()
                if result:
                    logger.info(f"User responded to invitation {invitation_id}: {new_status}")
                    return True
                else:
                    logger.warning(f"Invitation {invitation_id} not found or already responded")
                    return False
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to respond to invitation {invitation_id}: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def get_employees(self, business_id: int, status: str = 'accepted') -> list:
        """Get employees of a business"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT e.id, e.user_id, e.status, e.invited_at, e.responded_at,
                           u.username, u.first_name, u.last_name
                    FROM employees e
                    JOIN users u ON e.user_id = u.user_id
                    WHERE e.business_id = %s AND e.status = %s
                    ORDER BY e.invited_at DESC
                """, (business_id, status))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get employees for business {business_id}: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def get_all_employees(self, business_id: int) -> list:
        """Get all employees (all statuses) of a business"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT e.id, e.user_id, e.status, e.invited_at, e.responded_at,
                           u.username, u.first_name, u.last_name
                    FROM employees e
                    JOIN users u ON e.user_id = u.user_id
                    WHERE e.business_id = %s
                    ORDER BY e.status, e.invited_at DESC
                """, (business_id,))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get all employees for business {business_id}: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def is_business_owner(self, user_id: int) -> bool:
        """Check if user is a business owner"""
        business = self.get_business(user_id)
        return business is not None

    def is_employee(self, user_id: int, business_id: int = None) -> bool:
        """Check if user is an employee (of a specific business or any business)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                if business_id:
                    cursor.execute("""
                        SELECT 1 FROM employees 
                        WHERE user_id = %s AND business_id = %s AND status = 'accepted'
                    """, (user_id, business_id))
                else:
                    cursor.execute("""
                        SELECT 1 FROM employees 
                        WHERE user_id = %s AND status = 'accepted'
                    """, (user_id,))
                return cursor.fetchone() is not None
        finally:
            self.db.return_connection(conn)

    def get_user_businesses(self, user_id: int) -> list:
        """Get all businesses where user is an employee"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT b.id, b.business_name, b.owner_id,
                           u.username as owner_username, u.first_name as owner_first_name
                    FROM employees e
                    JOIN businesses b ON e.business_id = b.id
                    JOIN users u ON b.owner_id = u.user_id
                    WHERE e.user_id = %s AND e.status = 'accepted'
                    ORDER BY b.business_name
                """, (user_id,))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get businesses for user {user_id}: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def remove_employee(self, business_id: int, user_id: int) -> bool:
        """Remove an employee from a business"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM employees 
                    WHERE business_id = %s AND user_id = %s
                    RETURNING id
                """, (business_id, user_id))
                result = cursor.fetchone()
                conn.commit()
                if result:
                    logger.info(f"Removed employee {user_id} from business {business_id}")
                    return True
                else:
                    logger.warning(f"Employee {user_id} not found in business {business_id}")
                    return False
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to remove employee: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    
    def update_employee_rating(self, business_id: int, user_id: int, 
                              rating_change: int) -> Optional[int]:
        """
        Update employee rating by adding/subtracting points
        Rating is clamped between 0 and 1000
        
        Args:
            business_id: ID of the business
            user_id: ID of the employee
            rating_change: Amount to add (positive) or subtract (negative)
        
        Returns:
            New rating value or None if employee not found
        """
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE employees 
                    SET rating = GREATEST(0, LEAST(1000, rating + %s))
                    WHERE business_id = %s AND user_id = %s AND status = 'accepted'
                    RETURNING rating
                """, (rating_change, business_id, user_id))
                result = cursor.fetchone()
                conn.commit()
                if result:
                    new_rating = result[0]
                    logger.info(f"Updated rating for employee {user_id} in business {business_id}: change={rating_change}, new_rating={new_rating}")
                    return new_rating
                else:
                    logger.warning(f"Employee {user_id} not found in business {business_id}")
                    return None
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update employee rating: {e}")
            return None
        finally:
            self.db.return_connection(conn)
    
    def get_employee_rating(self, business_id: int, user_id: int) -> Optional[int]:
        """Get employee rating in a specific business"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT rating FROM employees
                    WHERE business_id = %s AND user_id = %s AND status = 'accepted'
                """, (business_id, user_id))
                result = cursor.fetchone()
                return result[0] if result else None
        finally:
            self.db.return_connection(conn)
    
    # Task management methods

    def create_task(self, business_id: int, title: str, description: str,
                   created_by: int, ai_recommended_employee: int = None) -> dict:
        """Create a new task"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO tasks (business_id, title, description, created_by, 
                                     ai_recommended_employee, status)
                    VALUES (%s, %s, %s, %s, %s, 'available')
                    RETURNING *
                """, (business_id, title, description, created_by, ai_recommended_employee))
                conn.commit()
                result = cursor.fetchone()
                logger.info(f"Created task {result['id']} for business {business_id}")
                return dict(result)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create task: {e}")
            raise
        finally:
            self.db.return_connection(conn)

    def get_task(self, task_id: int) -> Optional[dict]:
        """Get task by ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT t.*, 
                           u1.username as created_by_username, u1.first_name as created_by_name,
                           u2.username as assigned_to_username, u2.first_name as assigned_to_name,
                           u3.username as recommended_username, u3.first_name as recommended_name
                    FROM tasks t
                    LEFT JOIN users u1 ON t.created_by = u1.user_id
                    LEFT JOIN users u2 ON t.assigned_to = u2.user_id
                    LEFT JOIN users u3 ON t.ai_recommended_employee = u3.user_id
                    WHERE t.id = %s
                """, (task_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        finally:
            self.db.return_connection(conn)

    def get_available_tasks(self, business_id: int) -> list:
        """Get all available (unassigned) tasks for a business"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT t.*, 
                           u1.username as created_by_username, u1.first_name as created_by_name,
                           u2.username as recommended_username, u2.first_name as recommended_name
                    FROM tasks t
                    LEFT JOIN users u1 ON t.created_by = u1.user_id
                    LEFT JOIN users u2 ON t.ai_recommended_employee = u2.user_id
                    WHERE t.business_id = %s AND t.status = 'available'
                    ORDER BY t.created_at DESC
                """, (business_id,))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get available tasks: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def get_assigned_tasks(self, user_id: int, include_completed: bool = False) -> list:
        """Get tasks assigned to a user"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if include_completed:
                    status_filter = "AND t.status IN ('assigned', 'in_progress', 'completed')"
                else:
                    status_filter = "AND t.status IN ('assigned', 'in_progress')"

                cursor.execute(f"""
                    SELECT t.*, 
                           u.username as created_by_username, u.first_name as created_by_name,
                           b.business_name
                    FROM tasks t
                    LEFT JOIN users u ON t.created_by = u.user_id
                    LEFT JOIN businesses b ON t.business_id = b.id
                    WHERE t.assigned_to = %s {status_filter}
                    ORDER BY t.created_at DESC
                """, (user_id,))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get assigned tasks: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def get_business_tasks(self, business_id: int, status: str = None) -> list:
        """Get all tasks for a business, optionally filtered by status"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if status:
                    query = """
                        SELECT t.*, 
                               u1.username as created_by_username, u1.first_name as created_by_name,
                               u2.username as assigned_to_username, u2.first_name as assigned_to_name,
                               u3.username as abandoned_by_username, u3.first_name as abandoned_by_name
                        FROM tasks t
                        LEFT JOIN users u1 ON t.created_by = u1.user_id
                        LEFT JOIN users u2 ON t.assigned_to = u2.user_id
                        LEFT JOIN users u3 ON t.abandoned_by = u3.user_id
                        WHERE t.business_id = %s AND t.status = %s
                        ORDER BY t.created_at DESC
                    """
                    cursor.execute(query, (business_id, status))
                else:
                    query = """
                        SELECT t.*, 
                               u1.username as created_by_username, u1.first_name as created_by_name,
                               u2.username as assigned_to_username, u2.first_name as assigned_to_name,
                               u3.username as abandoned_by_username, u3.first_name as abandoned_by_name
                        FROM tasks t
                        LEFT JOIN users u1 ON t.created_by = u1.user_id
                        LEFT JOIN users u2 ON t.assigned_to = u2.user_id
                        LEFT JOIN users u3 ON t.abandoned_by = u3.user_id
                        WHERE t.business_id = %s
                        ORDER BY t.created_at DESC
                    """
                    cursor.execute(query, (business_id,))

                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get business tasks: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def assign_task(self, task_id: int, user_id: int, assigned_by: int) -> bool:
        """Assign a task to a user"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE tasks 
                    SET assigned_to = %s, 
                        status = 'assigned',
                        assigned_at = CURRENT_TIMESTAMP,
                        abandoned_by = NULL,
                        abandoned_at = NULL
                    WHERE id = %s AND status IN ('available', 'abandoned')
                    RETURNING id
                """, (user_id, task_id))
                result = cursor.fetchone()
                conn.commit()
                if result:
                    logger.info(f"Task {task_id} assigned to user {user_id} by {assigned_by}")
                    return True
                else:
                    logger.warning(f"Task {task_id} not available for assignment")
                    return False
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to assign task: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def take_task(self, task_id: int, user_id: int) -> bool:
        """Employee takes a task"""
        return self.assign_task(task_id, user_id, user_id)

    def complete_task(self, task_id: int, user_id: int) -> bool:
        """Mark task as completed"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE tasks 
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND assigned_to = %s 
                    AND status IN ('assigned', 'in_progress')
                    RETURNING id
                """, (task_id, user_id))
                result = cursor.fetchone()
                if result:
                    cursor.execute("""
                    UPDATE users 
                    SET completed_tasks = COALESCE(completed_tasks, 0) + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    """, (user_id,))
                conn.commit()
                if result:
                    logger.info(f"Task {task_id} completed by user {user_id}")
                    return True
                else:
                    logger.warning(f"Task {task_id} cannot be completed by user {user_id}")
                    return False
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to complete task: {e}")
            return False
        finally:
            self.db.return_connection(conn)

    def get_employee_task_history(self, user_id: int, business_id: int) -> list:
        """Get completed tasks history for an employee (for AI recommendations)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, description, completed_at
                    FROM tasks
                    WHERE assigned_to = %s 
                    AND business_id = %s 
                    AND status = 'completed'
                    ORDER BY completed_at DESC
                    LIMIT 10
                """, (user_id, business_id))
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get task history: {e}")
            return []
        finally:
            self.db.return_connection(conn)

    def get_all_employees_task_history(self, business_id: int) -> dict:
        """Get task history for all employees of a business (for AI recommendations)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT e.user_id, u.username, u.first_name,
                           COUNT(t.id) as completed_tasks,
                           u.abandonments_count,
                           ARRAY_AGG(t.title ORDER BY t.completed_at DESC) as task_titles,
                           ARRAY_AGG(t.description ORDER BY t.completed_at DESC) as task_descriptions,
                           ARRAY_AGG(
                               EXTRACT(EPOCH FROM (t.completed_at - t.assigned_at))/3600 
                               ORDER BY t.completed_at DESC
                           ) as task_hours
                    FROM employees e
                    JOIN users u ON e.user_id = u.user_id
                    LEFT JOIN tasks t ON t.assigned_to = e.user_id 
                        AND t.business_id = %s 
                        AND t.status = 'completed'
                        AND t.assigned_at IS NOT NULL
                        AND t.completed_at IS NOT NULL
                    WHERE e.business_id = %s AND e.status = 'accepted'
                    GROUP BY e.user_id, u.username, u.first_name, u.abandonments_count
                """, (business_id, business_id))
                results = cursor.fetchall()

                # Format results
                employees_history = {}
                for row in results:
                    # Filter out None values and limit to 10 recent tasks
                    task_titles = [t for t in (row['task_titles'] or []) if t][:10]
                    task_descriptions = [d for d in (row['task_descriptions'] or []) if d][:10]
                    task_hours = [h for h in (row['task_hours'] or []) if h is not None][:10]

                    employees_history[row['user_id']] = {
                        'username': row['username'],
                        'first_name': row['first_name'],
                        'completed_tasks': row['completed_tasks'],
                        'abandonments_count': row.get('abandonments_count', 0) or 0,
                        'task_titles': task_titles,
                        'task_descriptions': task_descriptions,
                        'task_hours': task_hours  # Time in hours to complete each task
                    }

                return employees_history
        except Exception as e:
            logger.error(f"Failed to get employees task history: {e}")
            return {}
        finally:
            self.db.return_connection(conn)

    def abandon_task(self, task_id: int, user_id: int) -> bool:
        """Employee abandons a taken task - меняет статус на 'abandoned'"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE tasks 
                    SET status = 'abandoned',
                        abandoned_by = %s,
                        abandoned_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND assigned_to = %s 
                    AND status IN ('assigned', 'in_progress')
                    RETURNING id
                """, (user_id, task_id, user_id))
                result = cursor.fetchone()
                if result:
                    cursor.execute("""
                        UPDATE users 
                        SET abandonments_count = COALESCE(abandonments_count, 0) + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                    """, (user_id,))
                conn.commit()
                if result:
                    logger.info(f"Task {task_id} abandoned by user {user_id}")
                    return True
                else:
                    logger.warning(f"Task {task_id} cannot be abandoned by user {user_id}")
                    return False
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to abandon task: {e}")
            return False
        finally:
            self.db.return_connection(conn)

# Global database instance
db = Database()
user_repo = UserRepository(db)
business_repo = BusinessRepository(db)

