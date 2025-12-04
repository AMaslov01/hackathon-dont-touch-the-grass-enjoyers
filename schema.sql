-- Database schema for Telegram AI Bot
-- PostgreSQL
-- Complete schema with all features (businesses, employees, search info)

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    user_info TEXT,
    overall_rating INTEGER,
    tokens INTEGER NOT NULL DEFAULT 0,
    max_tokens INTEGER NOT NULL DEFAULT 100,
    last_token_refresh TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    business_info TEXT,
    workers_info TEXT,
    executors_info TEXT,
    completed_tasks INTEGER DEFAULT 0,
    abandonments_count INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Businesses table
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
);

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    invited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    UNIQUE(business_id, user_id)
);

-- Usage history table
CREATE TABLE IF NOT EXISTS usage_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    tokens_used INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tasks table
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
);

-- Create indexes for better query performance

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_usage_history_user_id ON usage_history(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_history_created_at ON usage_history(created_at);

-- Businesses table indexes
CREATE INDEX IF NOT EXISTS idx_businesses_owner_id ON businesses(owner_id);

-- Employees table indexes
CREATE INDEX IF NOT EXISTS idx_employees_business_id ON employees(business_id);
CREATE INDEX IF NOT EXISTS idx_employees_user_id ON employees(user_id);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);

CREATE INDEX IF NOT EXISTS idx_tasks_business_id ON tasks(business_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

-- Comments for documentation

-- Users table comments
COMMENT ON TABLE users IS 'Stores user information and token balance';
COMMENT ON COLUMN users.user_id IS 'Telegram user ID (primary key)';
COMMENT ON COLUMN users.user_info IS 'User personal description for AI candidate matching';
COMMENT ON COLUMN users.overall_rating IS 'Overall user rating from last job (null if never employed)';
COMMENT ON COLUMN users.tokens IS 'Current available tokens';
COMMENT ON COLUMN users.max_tokens IS 'Maximum tokens after refresh';
COMMENT ON COLUMN users.last_token_refresh IS 'Last time tokens were refreshed';
COMMENT ON COLUMN users.business_info IS 'Legacy field - stored business information (deprecated, use businesses table)';
COMMENT ON COLUMN users.workers_info IS 'Stored information about workers/employees search requests';
COMMENT ON COLUMN users.executors_info IS 'Stored information about executors/freelancers search requests';

-- Businesses table comments
COMMENT ON TABLE businesses IS 'Stores business information for users';
COMMENT ON COLUMN businesses.owner_id IS 'Reference to the user who owns this business';
COMMENT ON COLUMN businesses.business_name IS 'Name of the business';
COMMENT ON COLUMN businesses.business_type IS 'Type/description of the business';
COMMENT ON COLUMN businesses.financial_situation IS 'Current financial situation of the business';
COMMENT ON COLUMN businesses.goals IS 'Business goals and objectives';

-- Employees table comments
COMMENT ON TABLE employees IS 'Stores employee invitations and associations with businesses';
COMMENT ON COLUMN employees.business_id IS 'Reference to the business';
COMMENT ON COLUMN employees.user_id IS 'Reference to the user (employee)';
COMMENT ON COLUMN employees.status IS 'Invitation status: pending, accepted, or declined';
COMMENT ON COLUMN employees.invited_at IS 'When the invitation was sent';
COMMENT ON COLUMN employees.responded_at IS 'When the user responded to the invitation';

-- Usage history table comments
COMMENT ON TABLE usage_history IS 'Logs all AI requests and responses';
COMMENT ON COLUMN usage_history.tokens_used IS 'Number of tokens deducted for this request';

