# Catalog 目录说明（中文）

`catalog/` 用于存放**内置模板配置**与**种子文件**，并随仓库版本管理。

可以把它理解为系统的“模板基线层”：

- 放稳定的默认配置；
- 通过 Git 管理变更；
- 不存放运行时状态数据。

## 目录结构

```text
catalog/
  README.md
  README.zh-CN.md
  default_users.yaml
  agents/
    {agent_id}.yaml
  workflow_templates/
    {workflow_template_id}/
      workflow_template.yaml
      agents/
        {agent_id}.yaml
  resource_configs/
    {resource_id}.yaml
```

## 关键目录与文件含义

### `default_users.yaml`

开发环境默认用户种子文件。  
后端启动时，当 users 表为空，会从这里初始化用户。

通常包含：

- 登录邮箱
- 展示名称
- 角色
- 默认密码（仅用于本地/开发）

### `agents/`

全局 Agent 模板库。  
每个 `{agent_id}.yaml` 表示一个可复用 Agent 模板。

常见字段包括：

- `role`
- `prompt`
- `tool/resource/skill` 绑定
- `react_config`（模型与推理参数）
- `enabled`

这些模板由 Agent 模板管理接口/UI 维护，是工作流模板编排可引用的基础模板。

### `workflow_templates/`

内置 Workflow Template 模板目录。  
每个 `{workflow_template_id}` 目录对应一个模板：

- `workflow_template.yaml`：流程元数据与图结构（`nodes`、`edges`、`entry_node`、`report_node`）
- `agents/`：该模板引用的 Agent 定义

边界说明（重要）：

- 这里是“模板配置层”；
- 运行时 runs/outputs 不应写到这里；
- 运行时数据统一落在 `.dd_project/`（例如 `.dd_project/users/{user_id}/{workflow_template_id}/{engagement_id}/sessions/{session_id}/runs/`）。

### `resource_configs/`

内置平台资源连接器配置。  
例如公开网页、文件库、数据库类连接器等。

项目运行时覆盖配置应写入 `.dd_project/data/platform/resource_configs`（或你配置的数据根目录），而不是修改这里的基线文件。

## 维护规则（建议）

- 基线模板变更：修改 `catalog/` 并走 Git 提交评审；
- 项目/用户/运行态数据：写入 `.dd_project/`；
- 避免把模板和运行态产物混放在同一路径。

