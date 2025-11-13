-- Database schema for Telegram AI Bot
-- PostgreSQL

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    tokens INTEGER NOT NULL DEFAULT 0,
    max_tokens INTEGER NOT NULL DEFAULT 100,
    last_token_refresh TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_usage_history_user_id ON usage_history(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_history_created_at ON usage_history(created_at);

-- Comments for documentation
COMMENT ON TABLE users IS 'Stores user information and token balance';
COMMENT ON COLUMN users.user_id IS 'Telegram user ID (primary key)';
COMMENT ON COLUMN users.tokens IS 'Current available tokens';
COMMENT ON COLUMN users.max_tokens IS 'Maximum tokens after refresh';
COMMENT ON COLUMN users.last_token_refresh IS 'Last time tokens were refreshed';

COMMENT ON TABLE usage_history IS 'Logs all AI requests and responses';
COMMENT ON COLUMN usage_history.tokens_used IS 'Number of tokens deducted for this request';

