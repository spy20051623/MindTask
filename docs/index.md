# MindTask Docs / MindTask 文档

Use these docs when you need more detail than the root `README.md`.

当你需要比根目录 `README.md` 更详细的信息时，请阅读这里的文档。

MindTask is developed with assistance from Codex.

MindTask 由 Codex 辅助开发。

## English

- [Getting Started](getting-started.en.md): first-time desktop UI setup and guided task workflow
- [Desktop Guide](desktop-guide.en.md): desktop workflows, task drawers, settings, shortcuts, and maintenance notes
- [CLI Reference](cli-reference.en.md): command list, options, and examples
- [Release Notes](release-notes.en.md): version-level development history

## 中文

- [新手入门](getting-started.zh.md)：首次使用桌面端、完成初始化设置，并走完整个任务流程
- [桌面端指南](desktop-guide.zh.md)：桌面端工作流、任务抽屉、设置、快捷键和维护说明
- [CLI 参考](cli-reference.zh.md)：命令列表、参数和示例
- [发布记录](release-notes.zh.md)：按版本记录的开发历史

The desktop UI reads local `config/mindtask.ini` first, then `%APPDATA%\MindTask\mindtask.ini`; if neither exists, it opens first-run setup. See the Desktop Guide for the full rule.

桌面端会优先读取软件目录旁的 `config/mindtask.ini`，其次读取 `%APPDATA%\MindTask\mindtask.ini`；如果两者都不存在，会进入首次设置。完整规则见桌面端指南。
