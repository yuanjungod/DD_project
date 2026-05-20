import type { PickerItem } from "../components/IdPickerSection";
import type {
  AgentTemplate,
  LibraryFile,
  Resource,
  ResourceConfig,
  SkillPackage,
  ToolConfig,
} from "../types/domain";

export function skillPickerItems(skills: SkillPackage[]): PickerItem[] {
  return [...skills]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((skill) => ({
      id: skill.id,
      name: skill.name || skill.id,
      hint: skill.description || skill.directory_name,
      enabled: skill.enabled,
    }));
}

export function toolPickerItems(tools: ToolConfig[]): PickerItem[] {
  return [...tools]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((tool) => ({
      id: tool.id,
      name: tool.name || tool.id,
      hint: tool.description || tool.implementation,
      enabled: tool.enabled,
    }));
}

export function resourceConfigPickerItems(resources: ResourceConfig[]): PickerItem[] {
  return [...resources]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((resource) => ({
      id: resource.id,
      name: resource.name || resource.id,
      hint: resource.description || resource.type,
      enabled: resource.enabled,
    }));
}

export function agentPickerItems(agentIds: string[], templates: AgentTemplate[]): PickerItem[] {
  const byId = new Map(templates.map((template) => [template.id, template]));
  return agentIds.map((id) => {
    const template = byId.get(id);
    return {
      id,
      name: template?.name ?? id,
      hint: template?.role ?? "",
      enabled: template?.enabled ?? true,
    };
  });
}

export function uploadFilePickerItems(projectResources: Resource[], libraryFiles: LibraryFile[]): PickerItem[] {
  const byId = new Map<string, PickerItem>();

  for (const row of projectResources) {
    if (row.type !== "file_reference") continue;
    const fileId = row.value.trim();
    if (!fileId) continue;
    const label = String(row.metadata_json?.label ?? row.metadata_json?.original_filename ?? fileId);
    byId.set(fileId, {
      id: fileId,
      name: label,
      hint: "应用文件库",
      enabled: true,
    });
  }

  for (const file of libraryFiles) {
    if (byId.has(file.id)) continue;
    byId.set(file.id, {
      id: file.id,
      name: file.original_filename || file.id,
      hint: "平台共享文件库",
      enabled: true,
    });
  }

  return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
}
