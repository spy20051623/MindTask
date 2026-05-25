CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    color TEXT DEFAULT '#007BFF',
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    project_id INTEGER,
    priority INTEGER DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
    status INTEGER DEFAULT 0 CHECK (status BETWEEN 0 AND 3),
    due_date TIMESTAMP,
    due_mode TEXT DEFAULT 'none' CHECK (due_mode IN ('none', 'all_day', 'exact_time')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS operation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    before_json TEXT,
    after_json TEXT,
    source TEXT DEFAULT 'user',
    ai_batch_id INTEGER,
    undone_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS database_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS ai_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT DEFAULT '',
    tool_name TEXT DEFAULT '',
    tool_call_id TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_operation_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    user_message_id INTEGER,
    model TEXT DEFAULT '',
    before_history_id INTEGER,
    after_history_id INTEGER,
    operation_summary_json TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    completed_at TIMESTAMP,
    undone_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due_date ON tasks(status, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_operation_history_created_at ON operation_history(created_at);
CREATE INDEX IF NOT EXISTS idx_operation_history_undone_at ON operation_history(undone_at);
CREATE INDEX IF NOT EXISTS idx_operation_history_ai_batch_id ON operation_history(ai_batch_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session_id ON ai_chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_operation_batches_session_id ON ai_operation_batches(session_id);

DROP TRIGGER IF EXISTS update_projects_timestamp;
DROP TRIGGER IF EXISTS update_tasks_timestamp;
DROP TRIGGER IF EXISTS update_ai_chat_sessions_timestamp;

CREATE TRIGGER update_projects_timestamp
AFTER UPDATE ON projects
BEGIN
    UPDATE projects SET updated_at = datetime('now', 'localtime') WHERE id = NEW.id;
END;

CREATE TRIGGER update_tasks_timestamp
AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = datetime('now', 'localtime') WHERE id = NEW.id;
END;

CREATE TRIGGER update_ai_chat_sessions_timestamp
AFTER UPDATE ON ai_chat_sessions
BEGIN
    UPDATE ai_chat_sessions SET updated_at = datetime('now', 'localtime') WHERE id = NEW.id;
END;

DROP VIEW IF EXISTS task_details;
DROP VIEW IF EXISTS tasks_with_tags;

CREATE VIEW task_details AS
SELECT
    t.id,
    t.title,
    t.description,
    t.project_id,
    p.name AS project_name,
    p.color AS project_color,
    t.priority,
    CASE t.priority
        WHEN 0 THEN 'None'
        WHEN 1 THEN 'Low'
        WHEN 2 THEN 'Medium'
        WHEN 3 THEN 'High'
        ELSE 'Unknown'
    END AS priority_text,
    t.status,
    CASE t.status
        WHEN 0 THEN 'not_started'
        WHEN 1 THEN 'in_progress'
        WHEN 2 THEN 'suspended'
        WHEN 3 THEN 'completed'
        ELSE 'Unknown'
    END AS status_text,
    t.due_date,
    t.due_mode,
    t.completed_at,
    t.created_at,
    t.updated_at
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id;
