# Task Plan

## Goal
整理项目中配置、资源、工作流、Agent 定义的冗余和冲突点，核心原则：可以落在文件目录中的配置和资源都以文件目录为主数据源，数据库/API/快照只做索引、运行时快照或用户数据。

## Current Task
收敛运行时配置、数据路径和默认用户来源：统一 writable data root，避免 SQLite/session 路径受启动目录影响，并将 dev 默认用户改为文件配置。

## Phases
- [complete] 1. 盘点现有配置/资源数据源与运行路径
- [complete] 2. 确定收敛策略与最小安全改动
- [complete] 3. 实施代码与文档更新
- [complete] 4. 验证前后端/agent_service 类型与关键路径
- [complete] 5. 增加 Agent step 输出目录与 README/资源落盘
- [complete] 6. 将前序输出目录地址注入下一个 Agent prompt/结果 schema
- [complete] 7. 验证串流、resume、前端类型兼容
- [complete] 8. 前端运行详情页展示每步 Agent 输出文件夹内容
- [complete] 9. 增加应用级 Agent overrides 存储、API、snapshot 合成与前端配置页
- [complete] 10. 统一数据路径、默认用户 seed 与文档说明

## Decisions
- 保持已发布运行快照可审计，不破坏历史 run。
- 新项目不做旧数据迁移兼容；只保留当前文件目录与运行快照所需入口。
- 文件目录作为配置主入口：场景 workflow 以 `agent_service/configs/scenario_templates` 为准，Agent 模板以 `agent_service/configs/agent_templates.yaml` 为准，skills 以 `agent_service/skills` 为启动源，tools 以 `tools.yaml` 镜像同步。
- 应用级 Agent 配置必须是 overlay/override，运行时合成 effective snapshot；不得修改场景模板或全局 Agent 模板。

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `ModuleNotFoundError: No module named 'yaml'` | 用系统 `python3` 直接 smoke-test file-backed loaders | 项目 `backend/requirements.txt` 已声明 `PyYAML`；保留语法检查与前端类型检查结果，最终说明该 smoke-test 受当前 shell 解释器依赖影响 |
| `SyntaxError` from running a Markdown skill file with `python3` | 误把 skill 文档路径当成 catchup 脚本执行 | 改为执行 planning-with-files 的 `session-catchup.py`，返回正常 |
