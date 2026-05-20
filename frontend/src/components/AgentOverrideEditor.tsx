import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteProjectAgentOverride, upsertProjectAgentOverride } from "../api/client";
import {
  IdMultiPickerSection,
  ResourceTypeMultiPickerSection,
  type PickerItem,
} from "./IdPickerSection";
import type { AgentTemplate, ProjectAgentOverride } from "../types/domain";

type OverrideConfigTab = "resources" | "skills" | "tools" | "prompt";

const OVERRIDE_CONFIG_TABS: { id: OverrideConfigTab; label: string }[] = [
  { id: "resources", label: "资源管理" },
  { id: "skills", label: "Skills" },
  { id: "tools", label: "工具" },
  { id: "prompt", label: "提示词" },
];

function overrideTabCount(draft: ProjectAgentOverride, tab: OverrideConfigTab): number {
  if (tab === "resources") {
    return draft.resource_ids_add.length + draft.resource_ids_remove.length;
  }
  if (tab === "skills") {
    return draft.skill_package_ids_add.length + draft.skill_package_ids_remove.length;
  }
  if (tab === "tools") {
    return draft.tool_ids_add.length + draft.tool_ids_remove.length;
  }
  return (draft.prompt_append.trim() ? 1 : 0) + (draft.prompt_override.trim() ? 1 : 0);
}

export function emptyOverride(agentId: string): ProjectAgentOverride {
  return {
    agent_id: agentId,
    prompt_append: "",
    prompt_override: "",
    skill_package_ids_add: [],
    skill_package_ids_remove: [],
    tool_ids_add: [],
    tool_ids_remove: [],
    resource_ids_add: [],
    resource_ids_remove: [],
    platform_upload_file_ids: [],
    react_config_override: {},
    enabled: true,
  };
}

export function AgentOverrideEditor({
  projectId,
  agentId,
  override,
  template,
  onRefresh,
  skillItems,
  toolItems,
  globalResourceItems,
  projectResourceItems,
  fileItems,
}: {
  projectId: string;
  agentId: string;
  override?: ProjectAgentOverride;
  template?: AgentTemplate;
  onRefresh: () => Promise<void>;
  skillItems: PickerItem[];
  toolItems: PickerItem[];
  globalResourceItems: PickerItem[];
  projectResourceItems: PickerItem[];
  fileItems: PickerItem[];
}) {
  const effective = override ?? emptyOverride(agentId);
  const [draft, setDraft] = useState<ProjectAgentOverride>(effective);
  const [activeTab, setActiveTab] = useState<OverrideConfigTab>("resources");
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState("");
  const [resourceSource, setResourceSource] = useState<"global" | "project">("project");

  const currentResourceItems = resourceSource === "project" ? projectResourceItems : globalResourceItems;
  const allResourceItems = useMemo(() => [...globalResourceItems, ...projectResourceItems], [globalResourceItems, projectResourceItems]);

  const tabCounts = useMemo(
    () =>
      Object.fromEntries(OVERRIDE_CONFIG_TABS.map((tab) => [tab.id, overrideTabCount(draft, tab.id)])) as Record<
        OverrideConfigTab,
        number
      >,
    [draft],
  );

  const templateSkillIds = useMemo(() => new Set(template?.skill_package_ids ?? []), [template?.skill_package_ids]);
  const templateToolIds = useMemo(() => new Set(template?.tool_ids ?? []), [template?.tool_ids]);
  const templateResourceIds = useMemo(() => new Set(template?.resource_ids ?? []), [template?.resource_ids]);

  const managedSkillIds = useMemo(() => {
    return skillItems
      .filter((item) =>
        templateSkillIds.has(item.id)
          ? !draft.skill_package_ids_remove.includes(item.id)
          : draft.skill_package_ids_add.includes(item.id),
      )
      .map((item) => item.id);
  }, [skillItems, templateSkillIds, draft.skill_package_ids_add, draft.skill_package_ids_remove]);

  const managedToolIds = useMemo(() => {
    return toolItems
      .filter((item) =>
        templateToolIds.has(item.id) ? !draft.tool_ids_remove.includes(item.id) : draft.tool_ids_add.includes(item.id),
      )
      .map((item) => item.id);
  }, [toolItems, templateToolIds, draft.tool_ids_add, draft.tool_ids_remove]);

  const managedResourceIds = useMemo(() => {
    return allResourceItems
      .filter((item) =>
        templateResourceIds.has(item.id)
          ? !draft.resource_ids_remove.includes(item.id)
          : draft.resource_ids_add.includes(item.id),
      )
      .map((item) => item.id);
  }, [allResourceItems, templateResourceIds, draft.resource_ids_add, draft.resource_ids_remove]);

  const handleSkillChange = useCallback(
    (nextSelected: string[]) => {
      const nextSet = new Set(nextSelected);
      const newAdd: string[] = [];
      const newRemove: string[] = [];
      for (const item of skillItems) {
        const inDefault = templateSkillIds.has(item.id);
        const checked = nextSet.has(item.id);
        if (inDefault) {
          if (!checked) newRemove.push(item.id);
        } else {
          if (checked) newAdd.push(item.id);
        }
      }
      setDraft((prev) => ({ ...prev, skill_package_ids_add: newAdd, skill_package_ids_remove: newRemove }));
    },
    [skillItems, templateSkillIds],
  );

  const handleToolChange = useCallback(
    (nextSelected: string[]) => {
      const nextSet = new Set(nextSelected);
      const newAdd: string[] = [];
      const newRemove: string[] = [];
      for (const item of toolItems) {
        const inDefault = templateToolIds.has(item.id);
        const checked = nextSet.has(item.id);
        if (inDefault) {
          if (!checked) newRemove.push(item.id);
        } else {
          if (checked) newAdd.push(item.id);
        }
      }
      setDraft((prev) => ({ ...prev, tool_ids_add: newAdd, tool_ids_remove: newRemove }));
    },
    [toolItems, templateToolIds],
  );

  const handleResourceChange = useCallback(
    (nextSelected: string[], scopeItems: PickerItem[]) => {
      const nextSet = new Set(nextSelected);
      const scopeSet = new Set(scopeItems.map((i) => i.id));
      const newAdd: string[] = [];
      const newRemove: string[] = [];
      for (const item of allResourceItems) {
        const inDefault = templateResourceIds.has(item.id);
        const inScope = scopeSet.has(item.id);
        const checked = inScope ? nextSet.has(item.id) : managedResourceIds.includes(item.id);
        if (inDefault) {
          if (!checked) newRemove.push(item.id);
        } else {
          if (checked) newAdd.push(item.id);
        }
      }
      setDraft((prev) => ({ ...prev, resource_ids_add: newAdd, resource_ids_remove: newRemove }));
    },
    [allResourceItems, templateResourceIds, managedResourceIds],
  );

  useEffect(() => {
    setDraft(effective);
    setActiveTab("resources");
    setResourceSource("project");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset editor when server override changes
  }, [agentId, JSON.stringify(override ?? {})]);

  async function save() {
    setSaving(true);
    setLocalError("");
    try {
      await upsertProjectAgentOverride(projectId, agentId, { ...draft, agent_id: agentId });
      await onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!override) return;
    setSaving(true);
    setLocalError("");
    try {
      await deleteProjectAgentOverride(projectId, agentId);
      await onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-override-card">
      <div className="agent-override-card__header">
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className="agent-override-card__avatar">{agentId.slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{agentId}</strong>
            <p className="muted">
              {override ? "已配置应用级覆盖；启动新 run 时会合成到快照。" : "继承场景模板配置，尚未配置应用级覆盖。"}
            </p>
          </div>
        </div>
        <label className="agent-override-enabled">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
            disabled={saving}
          />
          启用覆盖
        </label>
      </div>
      {localError ? <div className="error">{localError}</div> : null}
      <div className="agent-override-config-select-row">
        <label>
          <span>配置项</span>
          <select
            value={activeTab}
            onChange={(e) => setActiveTab(e.target.value as OverrideConfigTab)}
            disabled={saving}
          >
            {OVERRIDE_CONFIG_TABS.map((tab) => (
              <option key={tab.id} value={tab.id}>
                {tab.label}
                {tabCounts[tab.id] > 0 ? ` · ${tabCounts[tab.id]} 项` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="agent-override-config-panel">
        {activeTab === "prompt" ? (
          <>
            <label>
              追加提示词（继承模板后追加）
              <textarea
                rows={6}
                value={draft.prompt_append}
                onChange={(event) => setDraft({ ...draft, prompt_append: event.target.value })}
                disabled={saving}
                placeholder="在场景模板 prompt 之后追加本应用专属说明…"
              />
            </label>
            <label>
              覆盖提示词（填写后替代模板 prompt）
              <textarea
                rows={6}
                value={draft.prompt_override}
                onChange={(event) => setDraft({ ...draft, prompt_override: event.target.value })}
                disabled={saving}
                placeholder="填写后将完全替代模板中的系统提示词…"
              />
            </label>
          </>
        ) : null}
        {activeTab === "skills" ? (
          <IdMultiPickerSection
            title="Skills 管理"
            description="勾选表示在 Run 中使用该 Skill；取消勾选表示不使用。"
            items={skillItems}
            selected={managedSkillIds}
            onChange={handleSkillChange}
            disabled={saving}
            emptyText="暂无可用 Skill"
          />
        ) : null}
        {activeTab === "tools" ? (
          <IdMultiPickerSection
            title="工具管理"
            description="勾选表示在 Run 中使用该工具；取消勾选表示不使用。"
            items={toolItems}
            selected={managedToolIds}
            onChange={handleToolChange}
            disabled={saving}
            emptyText="暂无可用工具"
          />
        ) : null}
        {activeTab === "resources" ? (
          <>
            <nav className="resource-kind-tabs" aria-label="资源来源">
              <button
                type="button"
                className={`resource-kind-tab ${resourceSource === "project" ? "is-active" : ""}`}
                onClick={() => setResourceSource("project")}
                disabled={saving}
              >
                应用资源
              </button>
              <button
                type="button"
                className={`resource-kind-tab ${resourceSource === "global" ? "is-active" : ""}`}
                onClick={() => setResourceSource("global")}
                disabled={saving}
              >
                全局资源
              </button>
            </nav>
            <ResourceTypeMultiPickerSection
              title={resourceSource === "project" ? "应用资源管理" : "全局资源管理"}
              description="勾选表示在 Run 中使用该资源；取消勾选表示不使用。"
              typeHint="已选资源会在当前 Agent 的运行快照中生效。"
              items={currentResourceItems}
              selected={managedResourceIds}
              onChange={(ids) => handleResourceChange(ids, currentResourceItems)}
              disabled={saving}
              emptyText="该来源下暂无可用资源配置，请先在「公司资源」或「平台资源」中登记。"
            />

          </>
        ) : null}
      </div>
      <div className="inline-form" style={{ flexWrap: "wrap" }}>
        <button type="button" onClick={() => void save()} disabled={saving}>
          {saving ? "保存中…" : "保存应用级配置"}
        </button>
        <button type="button" className="secondary-button" onClick={() => void remove()} disabled={saving || !override}>
          删除覆盖，恢复继承模板
        </button>
      </div>
    </div>
  );
}
