# CLI 参考

CLI 是 MindTask 的脚本和调试接口。桌面端是主要用户体验；当你需要快速检查、自动化、导出或排查问题时，可以使用 CLI。

主入口：

```bash
python MindTask_cli.py <command> [options]
```

安装后也可以使用控制台命令：

```bash
mindtask <command> [options]
```

## 全局选项

使用自定义配置文件：

```bash
python MindTask_cli.py --config PATH <command> [options]
```

示例：

```bash
python MindTask_cli.py --config config/dev.ini list
```

数据库路径从当前配置文件读取。CLI 不提供直接传入数据库路径的选项。

## 常用取值

优先级取值：

```text
none | low | medium | high
0    | 1   | 2      | 3
```

状态取值：

```text
not_started | in_progress | suspended | completed
0           | 1           | 2         | 3
```

截止日期格式：

```text
YYYY-MM-DD HH:MM:SS
```

示例：

```text
2026-05-15 18:00:00
```

更新任务时，可以使用 `--due none` 清空截止日期。

## 项目

### 列出项目

格式：

```bash
python MindTask_cli.py projects
```

创建或更新任务前，可以用它查看项目 ID。

示例：

```bash
python MindTask_cli.py projects
```

输出格式：

```text
[1] Work  Work tasks
[2] Personal
```

### 创建项目

格式：

```bash
python MindTask_cli.py project-add NAME [--description TEXT] [--color HEX]
```

示例：

```bash
python MindTask_cli.py project-add Work
python MindTask_cli.py project-add Personal --description "Personal tasks"
python MindTask_cli.py project-add Reading --color "#7C3AED"
```

说明：

- `NAME` 必填。
- `--description` 可选。
- `--color` 默认是 `#007BFF`。

## 任务

### 列出任务

格式：

```bash
python MindTask_cli.py list [--project ID] [--status STATUS] [--priority 0|1|2|3] [--limit N] [--detailed] [--json]
```

示例：

```bash
python MindTask_cli.py list
python MindTask_cli.py list --detailed
python MindTask_cli.py list --project 1
python MindTask_cli.py list --status in_progress
python MindTask_cli.py list --priority 3
python MindTask_cli.py list --limit 10
python MindTask_cli.py list --json
```

说明：

- 默认按 ID 升序列出任务。
- `--project` 按项目 ID 筛选。
- `--status` 接受状态名称或数字。
- `--priority` 在列表筛选中只接受数字。
- `--detailed` 会显示项目、截止日期和详情。
- `--json` 会输出原始任务行 JSON。

### 创建任务

格式：

```bash
python MindTask_cli.py add TITLE [-d TEXT|--description TEXT] [-p ID|--project ID] [--priority PRIORITY] [--due "YYYY-MM-DD HH:MM:SS"]
```

示例：

```bash
python MindTask_cli.py add "Plan the week"
python MindTask_cli.py add "Write report" --priority high
python MindTask_cli.py add "Write report" --description "Draft the quarterly summary"
python MindTask_cli.py add "Prepare meeting" --project 1 --priority 2 --due "2026-05-15 18:00:00"
```

说明：

- `TITLE` 必填。
- 默认优先级是 `medium`。
- 如果需要项目 ID，请先运行 `projects`。
- 截止日期必须使用标准时间戳格式。

### 查看任务

格式：

```bash
python MindTask_cli.py show TASK_ID
```

示例：

```bash
python MindTask_cli.py show 12
```

该命令会以 JSON 输出完整任务行，包括紧凑列表中不会显示的字段。

### 更新任务

格式：

```bash
python MindTask_cli.py update TASK_ID [--title TEXT] [--description TEXT] [--project ID] [--priority PRIORITY] [--status STATUS] [--due VALUE]
```

示例：

```bash
python MindTask_cli.py update 12 --title "Plan next week"
python MindTask_cli.py update 12 --description "Update the draft plan"
python MindTask_cli.py update 12 --project 2
python MindTask_cli.py update 12 --priority high
python MindTask_cli.py update 12 --status in_progress
python MindTask_cli.py update 12 --due "2026-05-16 09:30:00"
python MindTask_cli.py update 12 --due none
python MindTask_cli.py update 12 --status suspended --priority low
```

说明：

- 至少需要提供一个要更新的字段。
- `--priority` 接受名称或数字。
- `--status` 接受名称或数字。
- `--due none` 会清空截止日期。
- 更新不存在的任务会返回非零退出码。

### 完成任务

格式：

```bash
python MindTask_cli.py complete TASK_ID
```

示例：

```bash
python MindTask_cli.py complete 12
```

该命令会把任务标记为已完成，并记录完成时间。

### 删除任务

格式：

```bash
python MindTask_cli.py delete TASK_ID [-y|--yes]
```

示例：

```bash
python MindTask_cli.py delete 12
python MindTask_cli.py delete 12 --yes
```

说明：

- 不带 `--yes` 时，CLI 会要求确认。
- 输入 `yes` 确认删除。
- 在脚本中无法交互确认时，可以使用 `--yes`。

## 搜索

### 搜索任务

格式：

```bash
python MindTask_cli.py search KEYWORD [--limit N] [--detailed] [--json]
```

示例：

```bash
python MindTask_cli.py search report
python MindTask_cli.py search "weekly plan" --detailed
python MindTask_cli.py search report --limit 5
python MindTask_cli.py search report --json
```

说明：

- 搜索使用核心任务搜索逻辑。
- 不传 `--limit` 时，会返回全部匹配任务。
- `--detailed` 会显示项目、截止日期和详情。

## 统计

### 显示统计

格式：

```bash
python MindTask_cli.py stats [--json]
```

示例：

```bash
python MindTask_cli.py stats
python MindTask_cli.py stats --json
```

文本输出包含任务总数、各状态数量、完成率和三天内即将到期任务数。

如果其他脚本需要解析结果，请使用 `--json`。

## 导出

### 导出任务

格式：

```bash
python MindTask_cli.py export [--format json|csv] [--output PATH] [--limit N]
```

示例：

```bash
python MindTask_cli.py export
python MindTask_cli.py export --format json --output tasks.json
python MindTask_cli.py export --format csv --output tasks.csv
python MindTask_cli.py export --limit 100
```

说明：

- 默认格式是 `json`。
- 不传 `--limit` 时，会导出全部任务。
- 不带 `--output` 时，导出内容会打印到标准输出。
- CSV 输出包含 ID、标题、详情、项目名称、优先级、状态、截止日期和创建时间等常用字段。

## 历史和回退

MindTask 会把写入操作记录到 `operation_history`。

### 显示历史

格式：

```bash
python MindTask_cli.py history [--limit N] [--all] [--json]
```

示例：

```bash
python MindTask_cli.py history
python MindTask_cli.py history --limit 20
python MindTask_cli.py history --all
python MindTask_cli.py history --json
```

说明：

- 不传 `--limit` 时，会返回全部匹配历史记录。
- 默认隐藏已经回退的操作。
- 使用 `--all` 可以包含已回退操作。
- 使用 `--json` 可以输出完整行数据。

### 回退最新操作

格式：

```bash
python MindTask_cli.py undo
```

示例：

```bash
python MindTask_cli.py undo
```

`undo` 会回退最新一条尚未回退的操作。

说明：

- 回退会修改数据。
- CLI 的回退命令只针对最新可回退操作。
- 如需可视化浏览历史或回退到某条选中记录，请使用桌面端历史抽屉。

## 版本

### 显示版本

格式：

```bash
python MindTask_cli.py version
```

示例：

```bash
python MindTask_cli.py version
```

该命令会打印包版本号。

## 常见流程

### 创建项目和任务

```bash
python MindTask_cli.py project-add Work --description "Work tasks"
python MindTask_cli.py projects
python MindTask_cli.py add "Write weekly report" --project 1 --priority high --due "2026-05-15 18:00:00"
python MindTask_cli.py list --project 1 --detailed
```

### 更新并完成任务

```bash
python MindTask_cli.py update 1 --status in_progress
python MindTask_cli.py update 1 --description "Draft is ready for review"
python MindTask_cli.py complete 1
python MindTask_cli.py show 1
```

### 导出小型 CSV

```bash
python MindTask_cli.py export --format csv --limit 50 --output tasks.csv
```

### 查看并回退最新修改

```bash
python MindTask_cli.py history --limit 5
python MindTask_cli.py undo
python MindTask_cli.py history --all --limit 5
```
