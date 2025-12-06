-- Migration: Add separate fields for local and cloud models
-- This fixes the issue when switching between AI_MODE modes

-- Add new columns for separate model tracking
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS current_local_model VARCHAR(100) DEFAULT 'llama3-finance',
ADD COLUMN IF NOT EXISTS current_cloud_model VARCHAR(100) DEFAULT 'deepseek-chimera';

-- Migrate existing current_model data based on model type
-- For users with existing current_model, determine if it's local or cloud
UPDATE users 
SET current_local_model = current_model
WHERE current_model IN ('llama3-finance', 'qwen2.5-7b');

UPDATE users 
SET current_cloud_model = current_model
WHERE current_model IN ('deepseek-chimera', 'meta-llama', 'glm-4.5-air');

-- The old current_model column can be kept for backwards compatibility
-- or dropped after migration is verified:
-- ALTER TABLE users DROP COLUMN IF EXISTS current_model;
