import { useEffect, useMemo, useState } from "react";

import {
  listAgentTemplates,
  listLibraryUploads,
  listProjectAgentOverrides,
  listProjectResourceConfigs,
  listResourceConfigs,
  listResources,
  listSkills,
  listToolConfigs,
  listWorkflowTemplates,
} from "../api/client";
import {
  resourceConfigPickerItems,
  skillPickerItems,
  toolPickerItems,
  uploadFilePickerItems,
} from "../domain/catalogPickerItems";
import { resolveGraphAgentOrder } from "../domain/workflowGraph";
import type { AgentTemplate, ProjectAgentOverride, WorkflowTemplate } from "../types/domain";
import { AgentOverrideEditor } from "./AgentOverrideEditor";
import { SectionCard } from "./SectionCard";

function workflowAgentIds(workflowTemplateId: string | undefined, workflowTemplates: WorkflowTemplate[]): string[] {
  const workflow = workflowTemplates.find((item) => item.id === workflowTemplateId);
  return resolveGraphAgentOrder(workflow?.graph);
}

export function ProjectAgentOverridesPanel({
  projectId,
  workflowTemplateId,
}: {
  projectId: string;
  workflowTemplateId?: string;
}) {
  const [agentOverrides, setAgentOverrides] = useState<ProjectAgentOverride[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [agentTemplates, setAgentTemplates] = useState<AgentTemplate[]>([]);
  const [skills, setSkills] = useState<Awaited<ReturnType<typeof listSkills>>>([]);
  const [tools, setTools] = useState<Awaited<ReturnType<typeof listToolConfigs>>>([]);
  const [resourceConfigs, setResourceConfigs] = useState<Awaited<ReturnType<typeof listResourceConfigs>>>([]);
  const [libraryFiles, setLibraryFiles] = useState<Awaited<ReturnType<typeof listLibraryUploads>>>([]);
  const [projectResourceConfigs, setProjectResourceConfigs] = useState<Awaited<ReturnType<typeof listProjectResourceConfigs>>>([]);
  const [resources, setResources] = useState<Awaited<ReturnType<typeof listResources>>>([]);
  const [error, setError] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");

  async function refresh() {
    const [overrideItems, workflowItems, resourceItems, companyResourceItems] = await Promise.all([
      listProjectAgentOverrides(projectId),
      listWorkflowTemplates(),
      listResources(projectId),
      listProjectResourceConfigs(projectId),
    ]);
    setAgentOverrides(overrideItems);
    setWorkflowTemplates(workflowItems);
    setResources(resourceItems);
    setProjectResourceConfigs(companyResourceItems);
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, [projectId]);

  useEffect(() => {
    Promise.all([listSkills(), listToolConfigs(), listResourceConfigs(), listLibraryUploads()])
      .then(([skillItems, toolItems, configItems, libraryItems]) => {
        setSkills(skillItems);
        setTools(toolItems);
        setResourceConfigs(configItems);
        setLibraryFiles(libraryItems);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    listAgentTemplates()
      .then(setAgentTemplates)
      .catch(() => {});
  }, []);

  const appAgentIds = workflowAgentIds(workflowTemplateId, workflowTemplates);

  useEffect(() => {
    if (appAgentIds.length > 0 && !selectedAgentId) {
      setSelectedAgentId(appAgentIds[0]);
    }
  }, [appAgentIds, selectedAgentId]);
  const skillItems = useMemo(() => skillPickerItems(skills), [skills]);
  const toolItems = useMemo(() => toolPickerItems(tools), [tools]);
  const globalResourceItems = useMemo(() => resourceConfigPickerItems(resourceConfigs), [resourceConfigs]);
  const projectResourceItems = useMemo(() => resourceConfigPickerItems(projectResourceConfigs), [projectResourceConfigs]);
  const fileItems = useMemo(() => uploadFilePickerItems(resources, libraryFiles), [resources, libraryFiles]);

  return (
    <SectionCard
      title="Agent 场景配置"
      description="在场景模板基础上为每个 Agent 配置提示词、Skills、工具与资源绑定；保存后会在启动 Run 时合成到快照。"
    >
      {error ? <div className="error">{error}</div> : null}
      <div className="agent-override-list">
        {appAgentIds.length === 0 ? (
          <p className="muted">当前应用尚未解析到工作流 Agent。</p>
        ) : (
          <>
            <div className="agent-select-row">
              <label>
                <span>配置 Agent</span>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                >
                  {appAgentIds.map((agentId) => {
                    const hasOverride = agentOverrides.some((o) => o.agent_id === agentId);
                    return (
                      <option key={agentId} value={agentId}>
                        {agentId}
                        {hasOverride ? " · 已配置" : ""}
                      </option>
                    );
                  })}
                </select>
              </label>
            </div>
            {selectedAgentId ? (
              <AgentOverrideEditor
                key={selectedAgentId}
                projectId={projectId}
                agentId={selectedAgentId}
                template={agentTemplates.find((t) => t.id === selectedAgentId)}
                override={agentOverrides.find((item) => item.agent_id === selectedAgentId)}
                onRefresh={refresh}
                skillItems={skillItems}
                toolItems={toolItems}
                globalResourceItems={globalResourceItems}
                projectResourceItems={projectResourceItems}
                fileItems={fileItems}
              />
            ) : null}
          </>
        )}
      </div>
    </SectionCard>
  );
}
