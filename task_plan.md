# Task Plan

## Goal
整理项目中配置、资源、工作流、Agent 定义的冗余和冲突点，核心原则：可以落在文件目录中的配置和资源都以文件目录为主数据源，数据库/API/快照只做索引、运行时快照或用户数据。

## Current Task
实现具体场景应用的 Agent 覆盖层：每个应用可在继承场景模板 Agent 配置后，单独追加/覆盖 prompt、skills、tools/resources、文件作用域等；覆盖只进入该应用的 run snapshot，不回写场景模板。

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

## Decisions
- 保持已发布运行快照可审计，不破坏历史 run。
- 不删除用户已有文件或模板；旧入口先降级为兼容 fallback，避免启动失败。
- 文件目录作为配置主入口：workflow/agent 以 workflow bundle 为准，skills 以 `agent_service/skills` 为启动源，tools 以 `tools.yaml` 镜像同步。
- 应用级 Agent 配置必须是 overlay/override，运行时合成 effective snapshot；不得修改 workflow bundle 模板。

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `ModuleNotFoundError: No module named 'yaml'` | 用系统 `python3` 直接 smoke-test file-backed loaders | 项目 `backend/requirements.txt` 已声明 `PyYAML`；保留语法检查与前端类型检查结果，最终说明该 smoke-test 受当前 shell 解释器依赖影响 |
