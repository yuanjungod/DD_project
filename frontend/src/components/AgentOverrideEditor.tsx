import { useEffect, useState } from "react";

import { deleteProjectAgentOverride, upsertProjectAgentOverride } from "../api/client";
import { IdMultiPickerSection, type PickerItem } from "./IdPickerSection";
import type { ProjectAgentOverride } from "../types/domain";

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
  onRefresh,
  skillItems,
  toolItems,
  resourceItems,
  fileItems,
}: {
  projectId: string;
  agentId: string;
  override?: ProjectAgentOverride;
  onRefresh: () => Promise<void>;
  skillItems: PickerItem[];
  toolItems: PickerItem[];
  resourceItems: PickerItem[];
  fileItems: PickerItem[];
}) {
  const effective = override ?? emptyOverride(agentId);
  const [draft, setDraft] = useState<ProjectAgentOverride>(effective);
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setDraft(effective);
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
        <div>
          <strong>{agentId}</strong>
          <p className="muted">
            {override ? "已配置应用级覆盖；启动新 run 时会合成到快照。" : "继承场景模板配置，尚未配置应用级覆盖。"}
          </p>
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
      <label>
        追加提示词（继承模板后追加）
        <textarea
          rows={3}
          value={draft.prompt_append}
          onChange={(event) => setDraft({ ...draft, prompt_append: event.target.value })}
          disabled={saving}
        />
      </label>
      <label>
        覆盖提示词（填写后替代模板 prompt）
        <textarea
          rows={3}
          value={draft.prompt_override}
          onChange={(event) => setDraft({ ...draft, prompt_override: event.target.value })}
          disabled={saving}
        />
      </label>
      <div className="grid two">
        <IdMultiPickerSection
          title="追加 Skill IDs"
          items={skillItems}
          selected={draft.skill_package_ids_add}
          onChange={(ids) => setDraft({ ...draft, skill_package_ids_add: ids })}
          disabled={saving}
          emptyText="暂无可用 Skill"
          compact
        />
        <IdMultiPickerSection
          title="移除模板 Skill IDs"
          items={skillItems}
          selected={draft.skill_package_ids_remove}
          onChange={(ids) => setDraft({ ...draft, skill_package_ids_remove: ids })}
          disabled={saving}
          emptyText="暂无可用 Skill"
          compact
        />
      </div>
      <div className="grid two">
        <IdMultiPickerSection
          title="追加工具 IDs"
          items={toolItems}
          selected={draft.tool_ids_add}
          onChange={(ids) => setDraft({ ...draft, tool_ids_add: ids })}
          disabled={saving}
          emptyText="暂无可用工具"
          compact
        />
        <IdMultiPickerSection
          title="移除模板工具 IDs"
          items={toolItems}
          selected={draft.tool_ids_remove}
          onChange={(ids) => setDraft({ ...draft, tool_ids_remove: ids })}
          disabled={saving}
          emptyText="暂无可用工具"
          compact
        />
      </div>
      <div className="grid two">
        <IdMultiPickerSection
          title="追加资源配置 IDs"
          items={resourceItems}
          selected={draft.resource_ids_add}
          onChange={(ids) => setDraft({ ...draft, resource_ids_add: ids })}
          disabled={saving}
          emptyText="暂无可用资源配置"
          compact
        />
        <IdMultiPickerSection
          title="移除模板资源配置 IDs"
          items={resourceItems}
          selected={draft.resource_ids_remove}
          onChange={(ids) => setDraft({ ...draft, resource_ids_remove: ids })}
          disabled={saving}
          emptyText="暂无可用资源配置"
          compact
        />
      </div>
      <IdMultiPickerSection
        title="本应用限定可见 file_id"
        description="留空表示继承默认可见范围；勾选后仅这些 file_id 对本 Agent 的 file_reader 可见。"
        items={fileItems}
        selected={draft.platform_upload_file_ids}
        onChange={(ids) => setDraft({ ...draft, platform_upload_file_ids: ids })}
        disabled={saving}
        emptyText="暂无可选 file_id，请先在应用资源中上传文件"
        compact
      />
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
