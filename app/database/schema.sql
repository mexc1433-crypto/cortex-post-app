-- Cortex Post Database Schema
-- SQLite / aiosqlite

-- ============================================================================
-- Users
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT DEFAULT 'ar',
    tier TEXT DEFAULT 'free' CHECK(tier IN ('free', 'premium')),
    premium_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Channels
-- ============================================================================
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel_telegram_id INTEGER UNIQUE NOT NULL,
    channel_title TEXT NOT NULL,
    channel_username TEXT,
    channel_type TEXT DEFAULT 'channel' CHECK(channel_type IN ('channel', 'group', 'supergroup')),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================================
-- Content Providers
-- ============================================================================
CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider_type TEXT NOT NULL CHECK(provider_type IN ('crypto', 'rss', 'sports', 'weather', 'religious', 'webhook')),
    name TEXT NOT NULL,
    config JSON NOT NULL,
    is_active INTEGER DEFAULT 1,
    last_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================================
-- Templates
-- ============================================================================
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    parse_mode TEXT DEFAULT 'HTML' CHECK(parse_mode IN ('HTML', 'Markdown', 'MarkdownV2')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================================
-- Rules
-- ============================================================================
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    provider_id INTEGER NOT NULL,
    template_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    conditions JSON NOT NULL,
    condition_logic TEXT DEFAULT 'AND' CHECK(condition_logic IN ('AND', 'OR')),
    is_active INTEGER DEFAULT 1,
    cooldown_minutes INTEGER DEFAULT 30,
    last_triggered_at TIMESTAMP,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

-- ============================================================================
-- Post Log
-- ============================================================================
CREATE TABLE IF NOT EXISTS post_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    provider_type TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'sent' CHECK(status IN ('sent', 'failed', 'pending')),
    platform TEXT DEFAULT 'telegram' CHECK(platform IN ('telegram', 'twitter')),
    telegram_message_id INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

-- ============================================================================
-- Webhook Events (incoming data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER,
    payload JSON NOT NULL,
    source_ip TEXT,
    processed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE SET NULL
);

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_channels_user_id ON channels(user_id);
CREATE INDEX IF NOT EXISTS idx_providers_user_id ON providers(user_id);
CREATE INDEX IF NOT EXISTS idx_templates_user_id ON templates(user_id);
CREATE INDEX IF NOT EXISTS idx_rules_user_id ON rules(user_id);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);
CREATE INDEX IF NOT EXISTS idx_post_log_rule_id ON post_log(rule_id);
CREATE INDEX IF NOT EXISTS idx_post_log_created_at ON post_log(created_at);
CREATE INDEX IF NOT EXISTS idx_webhook_events_processed ON webhook_events(processed);
