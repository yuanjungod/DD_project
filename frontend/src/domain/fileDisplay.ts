import { fileIdFromConfig, fileNameFromConfig } from "./resourceCatalogForm";
import type { LibraryFile, Resource, ResourceConfig } from "../types/domain";

/** Internal storage id (fil_*); not shown in user-facing copy. */
export function isInternalFileId(id: string): boolean {
  return /^fil_[a-zA-Z0-9_-]+$/.test(id.trim());
}

export function buildFileIdNameMap(
  libraryFiles: LibraryFile[] = [],
  projectResources: Resource[] = [],
  resourceConfigs: ResourceConfig[] = [],
): Map<string, string> {
  const map = new Map<string, string>();

  for (const file of libraryFiles) {
    const id = file.id.trim();
    if (!id) continue;
    map.set(id, file.original_filename?.trim() || "未命名文件");
  }

  for (const row of projectResources) {
    if (row.type !== "file_reference") continue;
    const id = row.value.trim();
    if (!id) continue;
    const meta = row.metadata_json ?? {};
    const name =
      (typeof meta.original_filename === "string" && meta.original_filename.trim()) ||
      (typeof meta.label === "string" && meta.label.trim()) ||
      "";
    if (name) map.set(id, name);
  }

  for (const resource of resourceConfigs) {
    if (resource.type !== "file_store") continue;
    const conn = resource.connection_config ?? {};
    const id = fileIdFromConfig(conn);
    if (!id) continue;
    const name = fileNameFromConfig(conn) || resource.name?.trim();
    if (name) map.set(id, name);
  }

  return map;
}

export function resolveFileDisplayName(fileId: string, lookup?: Map<string, string>): string {
  const id = fileId.trim();
  if (!id) return "—";
  const fromMap = lookup?.get(id)?.trim();
  if (fromMap) return fromMap;
  if (isInternalFileId(id)) return "未命名文件";
  return id;
}

export function resolveFileDisplayNames(fileIds: string[], lookup?: Map<string, string>): string[] {
  return fileIds.map((id) => resolveFileDisplayName(id, lookup));
}
