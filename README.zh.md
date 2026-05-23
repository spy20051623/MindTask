# MindTask

中文 | [English](README.md)

MindTask 是一个桌面优先的本地任务管理器，基于 SQLite 数据库。它面向日常任务管理，重点放在快速记录、清晰表格、实用抽屉、Markdown 详情、检查单草稿、项目筛选、历史回退和可预期的设置体验。

桌面 UI 是主要使用入口。CLI 命令用于脚本和调试。

MindTask 由 Codex 辅助开发。

## 亮点

- **基于 Markdown 的检查单编辑**：检查项从任务详情中解析，在专门的检查单区域编辑，并同步回 Markdown 草稿。
- **草稿优先的任务抽屉**：任务编辑、检查单修改和完成前检查都基于当前草稿进行，保存前不会写入数据库。
- **有范围的历史回退**：写入操作会被记录，可从历史抽屉回退，也可以从最新操作一直回退到选中的历史记录。
- **配置驱动的本地数据库切换**：可在桌面端数据设置中切换、创建、覆盖、重新加载和备份 SQLite 数据库，并进行路径和 schema 校验。
- **用抽屉组织桌面工作流**：新建任务、编辑任务、项目管理、最近任务历史和全局历史都使用右侧抽屉，而不是层层模态窗口。

## 主要功能

MindTask 当前包含：

- 任务创建、编辑、完成、删除和搜索
- Markdown 渲染任务详情
- 与 Markdown 同步的交互式检查单
- 截止日期模式：无截止日期、全天、精确时间
- 项目管理和项目筛选
- 包含超期未完成任务的即将到期筛选
- 紧凑表格中的状态和优先级展示
- 任务详情抽屉中的最近任务历史
- 全局操作历史和回退
- 英文和中文运行时本地化
- 浅色、深色和跟随系统主题
- 可配置键盘快捷键
- 数据库切换、创建、覆盖确认、重新加载和备份
- 用于自动化和调试的 CLI 命令

## 快速开始

安装 UI 依赖并打开桌面端：

```bash
pip install -e .[ui]
python MindTask_ui.py
```

首次启动时，MindTask 会先查找软件目录旁的 `config/mindtask.ini`，再查找系统路径 `%APPDATA%\MindTask\mindtask.ini`。如果两者都不存在，会打开欢迎设置流程。选择语言，选择配置文件创建位置，然后打开已有数据库或创建新数据库。

默认本地数据库是 `data/mindtask.db`。

## 文档

- [文档索引](docs/index.md)
- [新手入门](docs/getting-started.zh.md) / [English](docs/getting-started.en.md)
- [桌面端指南](docs/desktop-guide.zh.md) / [English](docs/desktop-guide.en.md)
- [CLI 参考](docs/cli-reference.zh.md) / [English](docs/cli-reference.en.md)
- [发布记录](docs/release-notes.zh.md) / [English](docs/release-notes.en.md)

## 项目结构

```text
MindTask/
  src/
    core/      SQLite 访问和业务逻辑
    cli/       脚本/调试命令接口
    ui/        PySide6 桌面 UI
  sql/         SQLite schema
  config/      配置模板
  docs/        用户和维护文档
```

## 配置

默认设置位于 `config/mindtask.ini.template`。当软件目录存在 `config/mindtask.ini` 时会优先使用它；否则使用 `%APPDATA%\MindTask\mindtask.ini`。数据库路径来自配置，也可以通过桌面端的数据设置页面修改。

本地数据库文件和生成的配置文件不应提交到仓库。

## 开发

安装开发依赖：

```bash
pip install -e .[dev]
```

常用检查：

```bash
python -m compileall src tests
pytest
```

构建 Windows 便携包：

```powershell
.\scripts\build_windows.ps1
```

构建输出位于 `dist\`。
便携应用目录和 zip 包中，`README.md`、`README.zh.md` 与 `docs` 会放在 `MindTask.exe` 同级。
