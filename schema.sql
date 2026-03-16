-- ══════════════════════════════════════════════════════════════════════════════
-- LexRisk Database Schema v2.0
-- Tracks user usage, caching, and tiered limits with PostgreSQL
-- ══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. USERS TABLE - Track user identities (IP or session-based)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(255) PRIMARY KEY,
    user_type VARCHAR(50) DEFAULT 'ip',  -- 'ip' or 'session'
    tier VARCHAR(20) DEFAULT 'free',     -- 'free', 'pro', 'business'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_analyses INTEGER DEFAULT 0,
    total_pages_processed INTEGER DEFAULT 0,
    total_text_chars INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_tier ON users(tier);
CREATE INDEX idx_users_last_seen ON users(last_seen);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. USAGE_LIMITS TABLE - Track daily usage per user
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_limits (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    limit_type VARCHAR(50) NOT NULL,     -- 'analysis', 'pages', 'text_chars'
    date DATE NOT NULL,
    count INTEGER DEFAULT 0,
    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, limit_type, date)
);

CREATE INDEX idx_usage_limits_user_date ON usage_limits(user_id, date);
CREATE INDEX idx_usage_limits_type ON usage_limits(limit_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. ANALYSIS_CACHE TABLE - Cache analysis results for identical contracts
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_cache (
    id SERIAL PRIMARY KEY,
    contract_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256 hash of contract text
    contract_length INTEGER NOT NULL,
    risk_score INTEGER NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    analysis_result JSONB NOT NULL,             -- Full analysis result
    engine_used VARCHAR(20) NOT NULL,           -- 'groq' or 'gemini'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cache_hash ON analysis_cache(contract_hash);
CREATE INDEX idx_cache_created ON analysis_cache(created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. ANALYSIS_HISTORY TABLE - Track all analysis requests
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    contract_hash VARCHAR(64) NOT NULL,
    contract_length INTEGER NOT NULL,
    page_count INTEGER DEFAULT 1,
    risk_score INTEGER,
    risk_level VARCHAR(20),
    engine_used VARCHAR(20),
    was_cached BOOLEAN DEFAULT FALSE,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_history_user ON analysis_history(user_id);
CREATE INDEX idx_history_created ON analysis_history(created_at);
CREATE INDEX idx_history_cached ON analysis_history(was_cached);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. TIER_LIMITS TABLE - Define limits per tier
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tier_limits (
    tier VARCHAR(20) PRIMARY KEY,
    daily_analyses INTEGER NOT NULL,
    max_pages_per_pdf INTEGER NOT NULL,
    max_text_chars INTEGER NOT NULL,
    priority_processing BOOLEAN DEFAULT FALSE,
    description TEXT
);

-- Insert default tier configurations
INSERT INTO tier_limits (tier, daily_analyses, max_pages_per_pdf, max_text_chars, priority_processing, description)
VALUES 
    ('free', 3, 2, 10000, FALSE, 'Free tier: 3 analyses/day, 2-page PDFs, 10k chars'),
    ('pro', 50, 100, 100000, TRUE, 'Pro tier: 50 analyses/day, 100-page PDFs, 100k chars'),
    ('business', -1, -1, -1, TRUE, 'Business tier: Unlimited analyses, unlimited pages, unlimited chars')
ON CONFLICT (tier) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. REDLINED_CLAUSES TABLE - Track which clauses get highlighted most often
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS redlined_clauses (
    id SERIAL PRIMARY KEY,
    clause_category VARCHAR(100) NOT NULL,
    clause_severity VARCHAR(20) NOT NULL,
    clause_text TEXT NOT NULL,
    contract_hash VARCHAR(64) NOT NULL,
    detection_count INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_redlined_category ON redlined_clauses(clause_category);
CREATE INDEX idx_redlined_severity ON redlined_clauses(clause_severity);

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. HELPER FUNCTIONS
-- ─────────────────────────────────────────────────────────────────────────────

-- Function to get or create user
CREATE OR REPLACE FUNCTION get_or_create_user(p_user_id VARCHAR, p_user_type VARCHAR DEFAULT 'ip', p_tier VARCHAR DEFAULT 'free')
RETURNS VOID AS $$
BEGIN
    INSERT INTO users (user_id, user_type, tier)
    VALUES (p_user_id, p_user_type, p_tier)
    ON CONFLICT (user_id) DO UPDATE
    SET last_seen = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Function to check if user has exceeded daily limit
CREATE OR REPLACE FUNCTION check_daily_limit(p_user_id VARCHAR, p_limit_type VARCHAR)
RETURNS TABLE(allowed BOOLEAN, remaining INTEGER, tier_name VARCHAR) AS $$
DECLARE
    v_tier VARCHAR;
    v_max_daily INTEGER;
    v_current_count INTEGER;
BEGIN
    -- Get user tier
    SELECT tier INTO v_tier FROM users WHERE user_id = p_user_id;
    
    IF v_tier IS NULL THEN
        v_tier := 'free';
    END IF;
    
    -- Get tier limit
    SELECT daily_analyses INTO v_max_daily FROM tier_limits WHERE tier = v_tier;
    
    -- Business tier has unlimited (-1)
    IF v_max_daily = -1 THEN
        RETURN QUERY SELECT TRUE, -1, v_tier;
        RETURN;
    END IF;
    
    -- Get current count for today
    SELECT COALESCE(count, 0) INTO v_current_count
    FROM usage_limits
    WHERE user_id = p_user_id 
        AND limit_type = p_limit_type 
        AND date = CURRENT_DATE;
    
    -- Return result
    RETURN QUERY SELECT 
        (v_current_count < v_max_daily) AS allowed,
        (v_max_daily - v_current_count) AS remaining,
        v_tier;
END;
$$ LANGUAGE plpgsql;

-- Function to increment usage
CREATE OR REPLACE FUNCTION increment_usage(
    p_user_id VARCHAR, 
    p_limit_type VARCHAR,
    p_pages INTEGER DEFAULT 1,
    p_text_chars INTEGER DEFAULT 0
)
RETURNS VOID AS $$
BEGIN
    -- Ensure user exists
    PERFORM get_or_create_user(p_user_id);
    
    -- Upsert usage count
    INSERT INTO usage_limits (user_id, limit_type, date, count)
    VALUES (p_user_id, p_limit_type, CURRENT_DATE, 1)
    ON CONFLICT (user_id, limit_type, date) 
    DO UPDATE SET 
        count = usage_limits.count + 1,
        last_reset = CURRENT_TIMESTAMP;
    
    -- Update user totals
    UPDATE users
    SET 
        total_analyses = total_analyses + 1,
        total_pages_processed = total_pages_processed + p_pages,
        total_text_chars = total_text_chars + p_text_chars,
        last_seen = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. ANALYTICS VIEWS
-- ─────────────────────────────────────────────────────────────────────────────

-- Daily usage summary
CREATE OR REPLACE VIEW daily_usage_summary AS
SELECT 
    date,
    COUNT(DISTINCT user_id) as unique_users,
    SUM(count) as total_analyses,
    AVG(count) as avg_analyses_per_user
FROM usage_limits
WHERE limit_type = 'analysis'
GROUP BY date
ORDER BY date DESC;

-- Tier distribution
CREATE OR REPLACE VIEW tier_distribution AS
SELECT 
    tier,
    COUNT(*) as user_count,
    AVG(total_analyses) as avg_analyses,
    SUM(total_pages_processed) as total_pages
FROM users
WHERE is_active = TRUE
GROUP BY tier;

-- Cache hit rate
CREATE OR REPLACE VIEW cache_performance AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_requests,
    SUM(CASE WHEN was_cached THEN 1 ELSE 0 END) as cached_requests,
    ROUND(100.0 * SUM(CASE WHEN was_cached THEN 1 ELSE 0 END) / COUNT(*), 2) as cache_hit_rate
FROM analysis_history
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Most detected predatory clauses
CREATE OR REPLACE VIEW top_predatory_clauses AS
SELECT 
    clause_category,
    clause_severity,
    COUNT(*) as detection_count,
    MIN(first_seen) as first_detected,
    MAX(last_seen) as last_detected
FROM redlined_clauses
GROUP BY clause_category, clause_severity
ORDER BY detection_count DESC
LIMIT 50;

-- ─────────────────────────────────────────────────────────────────────────────
-- 9. CLEANUP POLICIES (Optional - uncomment to enable)
-- ─────────────────────────────────────────────────────────────────────────────

-- Clean old cache entries (older than 30 days with low hit count)
-- DELETE FROM analysis_cache 
-- WHERE created_at < CURRENT_DATE - INTERVAL '30 days' 
-- AND hit_count < 2;

-- Clean old usage records (keep 90 days)
-- DELETE FROM usage_limits 
-- WHERE date < CURRENT_DATE - INTERVAL '90 days';

-- Clean old analysis history (keep 180 days)
-- DELETE FROM analysis_history 
-- WHERE created_at < CURRENT_DATE - INTERVAL '180 days';
