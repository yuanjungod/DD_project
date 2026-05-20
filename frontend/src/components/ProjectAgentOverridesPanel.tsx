import { useEffect, useMemo, useState } from "react";

import {
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
import type { ProjectAgentOverride, WorkflowTemplate } from "../types/domain";
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
  const [skills, setSkills] = useState<Awaited<ReturnType<typeof listSkills>>>([]);
  const [tools, setTools] = useState<Awaited<ReturnType<typeof listToolConfigs>>>([]);
  const [resourceConfigs, setResourceConfigs] = useState<Awaited<ReturnType<typeof listResourceConfigs>>>([]);
  const [libraryFiles, setLibraryFiles] = useState<Awaited<ReturnType<typeof listLibraryUploads>>>([]);
  const [projectResourceConfigs, setProjectResourceConfigs] = useState<Awaited<ReturnType<typeof listProjectResourceConfigs>>>([]);
  const [resources, setResources] = useState<Awaited<ReturnType<typeof listResources>>>([]);
  const [error, setError] = useState("");

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

  const appAgentIds = workflowAgentIds(workflowTemplateId, workflowTemplates);
  const skillItems = useMemo(() => skillPickerItems(skills), [skills]);
  const toolItems = useMemo(() => toolPickerItems(tools), [tools]);
  const resourceItems = useMemo(
    () => resourceConfigPickerItems([...resourceConfigs, ...projectResourceConfigs]),
    [resourceConfigs, projectResourceConfigs],
  );
  const fileItems = useMemo(() => uploadFilePickerItems(resources, libraryFiles), [resources, libraryFiles]);

  return (
    <SectionCard
      title="Agent 场景配置"
      description="在场景模板基础上为每个 Agent 配置提示词、Skills、工具与资源绑定；保存后会在启动 Run 时合成到快照。"
    >
      {error ? <div className="error">{error}</div> : null}
      <div className="agent-override-list">
        {appAgentIds.map((agentId) => (
          <AgentOverrideEditor
            key={agentId}
            projectId={projectId}
            agentId={agentId}
            override={agentOverrides.find((item) => item.agent_id === agentId)}
            onRefresh={refresh}
            skillItems={skillItems}
            toolItems={toolItems}
            resourceItems={resourceItems}
            fileItems={fileItems}
          />
        ))}
        {appAgentIds.length === 0 ? <p className="muted">当前应用尚未解析到工作流 Agent。</p> : null}
      </div>
    </SectionCard>
  );
}
