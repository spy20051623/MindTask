CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    color TEXT DEFAULT '#007BFF',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    project_id INTEGER,
    priority INTEGER DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
    status INTEGER DEFAULT 0 CHECK (status BETWEEN 0 AND 3),
    due_date TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#6C757D',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_tags (
    task_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, tag_id),
    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS operation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    before_json TEXT,
    after_json TEXT,
    undone_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due_date ON tasks(status, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_task_tags_task_id ON task_tags(task_id);
CREATE INDEX IF NOT EXISTS idx_task_tags_tag_id ON task_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_operation_history_created_at ON operation_history(created_at);
CREATE INDEX IF NOT EXISTS idx_operation_history_undone_at ON operation_history(undone_at);

CREATE TRIGGER IF NOT EXISTS update_projects_timestamp
AFTER UPDATE ON projects
BEGIN
    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_tasks_timestamp
AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
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
    t.completed_at,
    t.created_at,
    t.updated_at
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id;

CREATE VIEW tasks_with_tags AS
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
    t.completed_at,
    t.created_at,
    t.updated_at,
    GROUP_CONCAT(tg.name, ', ') AS tag_names,
    GROUP_CONCAT(tg.color, ', ') AS tag_colors
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
LEFT JOIN task_tags tt ON t.id = tt.task_id
LEFT JOIN tags tg ON tt.tag_id = tg.id
GROUP BY t.id;

INSERT INTO projects (name, description, color)
SELECT 'Work', 'Work-related tasks', '#007BFF'
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE name = 'Work');

INSERT INTO projects (name, description, color)
SELECT 'Personal', 'Personal life tasks', '#28A745'
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE name = 'Personal');

INSERT INTO projects (name, description, color)
SELECT 'Learning', 'Learning and growth tasks', '#FFC107'
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE name = 'Learning');

INSERT INTO projects (name, description, color)
SELECT 'Health', 'Health and exercise tasks', '#DC3545'
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE name = 'Health');

INSERT INTO tags (name, color)
SELECT 'Urgent', '#DC3545'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = 'Urgent');

INSERT INTO tags (name, color)
SELECT 'Important', '#FD7E14'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = 'Important');

INSERT INTO tags (name, color)
SELECT 'Quick', '#28A745'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = 'Quick');

INSERT INTO tags (name, color)
SELECT 'Waiting', '#6C757D'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = 'Waiting');

INSERT INTO tags (name, color)
SELECT 'Creative', '#17A2B8'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = 'Creative');
