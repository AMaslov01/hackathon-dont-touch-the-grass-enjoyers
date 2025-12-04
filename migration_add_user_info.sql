-- Migration to add user_info and overall_rating fields
-- Run this script to update existing database

-- Add user_info column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'user_info'
    ) THEN
        ALTER TABLE users ADD COLUMN user_info TEXT;
    END IF;
END $$;

-- Add overall_rating column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'overall_rating'
    ) THEN
        ALTER TABLE users ADD COLUMN overall_rating INTEGER;
    END IF;
END $$;

-- Add comments
COMMENT ON COLUMN users.user_info IS 'User personal description for AI candidate matching';
COMMENT ON COLUMN users.overall_rating IS 'Overall user rating from last job (null if never employed)';

