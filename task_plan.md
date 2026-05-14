# Task Plan

## Goal
整理项目中配置、资源、工作流、Agent 定义的冗余和冲突点，核心原则：可以落在文件目录中的配置和资源都以文件目录为主数据源，数据库/API/快照只做索引、运行时快照或用户数据。

## Phases
- [complete] 1. 盘点现有配置/资源数据源与运行路径
- [complete] 2. 确定收敛策略与最小安全改动
- [complete] 3. 实施代码与文档更新
- [complete] 4. 验证前后端/agent_service 类型与关键路径

## Decisions
- 保持已发布运行快照可审计，不破坏历史 run。
- 不删除用户已有文件或模板；旧入口先降级为兼容 fallback，避免启动失败。
- 文件目录作为配置主入口：workflow/agent 以 workflow bundle 为准，skills 以 `agent_service/skills` 为启动源，tools 以 `tools.yaml` 镜像同步。

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `ModuleNotFoundError: No module named 'yaml'` | 用系统 `python3` 直接 smoke-test file-backed loaders | 项目 `backend/requirements.txt` 已声明 `PyYAML`；保留语法检查与前端类型检查结果，最终说明该 smoke-test 受当前 shell 解释器依赖影响 |
