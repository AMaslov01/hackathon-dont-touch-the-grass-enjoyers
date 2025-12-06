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
    tokens INTEGER NOT NULL DEFAULT 50,
    max_tokens INTEGER NOT NULL DEFAULT 100,
    last_token_refresh TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_roulette_spin TIMESTAMP,
    roulette_notified BOOLEAN DEFAULT FALSE,
    workers_info TEXT,
    executors_info TEXT,
    completed_tasks INTEGER DEFAULT 0,
    abandonments_count INTEGER DEFAULT 0,
    active_business_id INTEGER,
    current_model VARCHAR(50) DEFAULT 'llama3-finance',  -- Default для local режима; для openrouter будет glm-4.5-air (устанавливается в коде)
    premium_expires_at TIMESTAMP,
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
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    rating INTEGER NOT NULL DEFAULT 500,
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
    deadline_minutes INTEGER,
    difficulty INTEGER CHECK (difficulty >= 1 AND difficulty <= 5),
    priority VARCHAR(20),
    submitted_at TIMESTAMP,
    quality_coefficient NUMERIC(3, 2) CHECK (quality_coefficient >= 0.5 AND quality_coefficient <= 1.0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Premium purchases table (for tracking premium access purchases)
CREATE TABLE IF NOT EXISTS premium_purchases (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    model_id VARCHAR(50) NOT NULL,
    tokens_spent INTEGER NOT NULL,
    days_purchased INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    purchased_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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

-- Premium purchases table indexes
CREATE INDEX IF NOT EXISTS idx_premium_purchases_user_id ON premium_purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_premium_purchases_expires_at ON premium_purchases(expires_at);

-- Users table indexes for new fields
CREATE INDEX IF NOT EXISTS idx_users_active_business ON users(active_business_id);
CREATE INDEX IF NOT EXISTS idx_users_premium_expires_at ON users(premium_expires_at) WHERE premium_expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_current_model ON users(current_model);

-- Comments for documentation

-- Users table comments
COMMENT ON TABLE users IS 'Stores user information and token balance';
COMMENT ON COLUMN users.user_id IS 'Telegram user ID (primary key)';
COMMENT ON COLUMN users.user_info IS 'User personal description for AI candidate matching';
COMMENT ON COLUMN users.overall_rating IS 'Overall user rating from last job (null if never employed)';
COMMENT ON COLUMN users.tokens IS 'Current available tokens';
COMMENT ON COLUMN users.max_tokens IS 'Maximum tokens after refresh';
COMMENT ON COLUMN users.last_token_refresh IS 'Last time tokens were refreshed';
COMMENT ON COLUMN users.last_roulette_spin IS 'Last time user spun the roulette';
COMMENT ON COLUMN users.roulette_notified IS 'Whether user has been notified about available roulette';
COMMENT ON COLUMN users.workers_info IS 'Stored information about workers/employees search requests';
COMMENT ON COLUMN users.executors_info IS 'Stored information about executors/freelancers search requests';
COMMENT ON COLUMN users.completed_tasks IS 'Total number of tasks completed by user';
COMMENT ON COLUMN users.abandonments_count IS 'Total number of tasks abandoned by user';
COMMENT ON COLUMN users.active_business_id IS 'Currently active business for the user';
COMMENT ON COLUMN users.current_model IS 'Currently selected AI model ID. Default: llama3-finance (local mode) or glm-4.5-air (openrouter mode)';
COMMENT ON COLUMN users.premium_expires_at IS 'Premium access expiration timestamp (NULL if no premium)';

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
COMMENT ON COLUMN employees.status IS 'Invitation status: pending, accepted, or rejected';
COMMENT ON COLUMN employees.rating IS 'Employee rating in this specific business (500 = default, 0-1000 range)';
COMMENT ON COLUMN employees.invited_at IS 'When the invitation was sent';
COMMENT ON COLUMN employees.responded_at IS 'When the user responded to the invitation';

-- Tasks table comments
COMMENT ON TABLE tasks IS 'Stores tasks for businesses';
COMMENT ON COLUMN tasks.business_id IS 'Reference to the business';
COMMENT ON COLUMN tasks.title IS 'Task title';
COMMENT ON COLUMN tasks.description IS 'Task description';
COMMENT ON COLUMN tasks.assigned_to IS 'User assigned to this task';
COMMENT ON COLUMN tasks.created_by IS 'User who created the task';
COMMENT ON COLUMN tasks.status IS 'Task status: available, assigned, in_progress, submitted, completed, abandoned';
COMMENT ON COLUMN tasks.ai_recommended_employee IS 'AI recommended employee for this task';
COMMENT ON COLUMN tasks.abandoned_by IS 'User who abandoned the task';
COMMENT ON COLUMN tasks.abandoned_at IS 'When the task was abandoned';
COMMENT ON COLUMN tasks.deadline_minutes IS 'Task deadline in minutes from assignment';
COMMENT ON COLUMN tasks.difficulty IS 'Task difficulty (1-5)';
COMMENT ON COLUMN tasks.priority IS 'Task priority: низкий, средний, высокий';
COMMENT ON COLUMN tasks.submitted_at IS 'When the task was submitted for review';
COMMENT ON COLUMN tasks.quality_coefficient IS 'Quality rating from owner (0.5-1.0)';

-- Usage history table comments
COMMENT ON TABLE usage_history IS 'Logs all AI requests and responses';
COMMENT ON COLUMN usage_history.tokens_used IS 'Number of tokens deducted for this request';

-- Premium purchases table comments
COMMENT ON TABLE premium_purchases IS 'Tracks premium access purchases';
COMMENT ON COLUMN premium_purchases.user_id IS 'User who purchased premium';
COMMENT ON COLUMN premium_purchases.model_id IS 'Model ID or premium_access for general premium';
COMMENT ON COLUMN premium_purchases.tokens_spent IS 'Amount of tokens spent';
COMMENT ON COLUMN premium_purchases.days_purchased IS 'Number of days purchased';
COMMENT ON COLUMN premium_purchases.expires_at IS 'When this premium access expires';
COMMENT ON COLUMN premium_purchases.purchased_at IS 'When the purchase was made';

