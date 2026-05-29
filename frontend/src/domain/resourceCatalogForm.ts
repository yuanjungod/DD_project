import type { PlatformResourceType } from "./platformResourceRegistry";
import type { ResourceConfig } from "../types/domain";

export function fileIdFromConfig(c: Record<string, unknown>): string {
  return typeof c.file_id === "string" ? c.file_id.trim() : "";
}

export function fileNameFromConfig(c: Record<string, unknown>): string {
  return typeof c.original_filename === "string" ? c.original_filename.trim() : "";
}

export function resourceNameFromUpload(filename: string): string {
  return filename.trim() || "未命名文件";
}

export function formatLibraryBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatFileStoreSize(c: Record<string, unknown>): string {
  const n = c.size_bytes;
  return typeof n === "number" ? formatLibraryBytes(n) : "";
}

export function buildFileStoreConnection(
  fields: Record<string, string>,
  fileMeta: { fileId: string; originalFilename: string; sizeBytes?: number },
): Record<string, unknown> {
  const base = buildConnection("file_store", fields);
  const out: Record<string, unknown> = { ...base };
  if (fileMeta.fileId.trim()) out.file_id = fileMeta.fileId.trim();
  if (fileMeta.originalFilename.trim()) out.original_filename = fileMeta.originalFilename.trim();
  if (fileMeta.sizeBytes != null) out.size_bytes = fileMeta.sizeBytes;
  return out;
}

export function labelsFor(tp: PlatformResourceType): Record<string, string> {
  switch (tp) {
    case "file_store":
      return {
        notes: "文件用途或策略说明（可选）",
      };
    case "mcp":
      return {
        server_name: "MCP 服务名称（可选登记）",
        transport: "传输方式（stdio / sse / http，可选登记）",
        endpoint: "连接地址或启动命令（可选登记）",
        notes: "权限与使用说明（可选）",
      };
    case "metrics_platform":
      return {
        provider: "系统（snowflake / databricks / custom，可选登记）",
        entity_key_field: "主体键字段（可选登记）",
        grain: "粒度（可选登记）",
        freshness_sla_hours: "数据新鲜度 SLA（小时，可选登记）",
        taxonomy_ref: "指标目录 / 数据字典链接（可选）",
        notes: "权限与脱敏说明（可选）",
      };
    default:
      return {};
  }
}

export function emptyFields(tp: PlatformResourceType): Record<string, string> {
  const keys = Object.keys(labelsFor(tp));
  return Object.fromEntries(keys.map((k) => [k, ""]));
}

export function fieldsFromConnection(tp: PlatformResourceType, c: Record<string, unknown>): Record<string, string> {
  const base = emptyFields(tp);
  switch (tp) {
    case "file_store":
      return {
        ...base,
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "mcp":
      return {
        ...base,
        server_name: String(c.server_name ?? ""),
        transport: String(c.transport ?? ""),
        endpoint: String(c.endpoint ?? ""),
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "metrics_platform":
      return {
        ...base,
        provider: String(c.provider ?? ""),
        entity_key_field: String(c.entity_key_field ?? ""),
        grain: String(c.grain ?? ""),
        freshness_sla_hours: c.freshness_sla_hours != null ? String(c.freshness_sla_hours) : "",
        taxonomy_ref: typeof c.taxonomy_ref === "string" ? c.taxonomy_ref : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    default:
      return base;
  }
}

export function buildConnection(tp: PlatformResourceType, f: Record<string, string>): Record<string, unknown> {
  const trim = (s: string) => s.trim();
  switch (tp) {
    case "file_store":
      return trim(f.notes) ? { notes: trim(f.notes) } : {};
    case "mcp":
      return {
        server_name: trim(f.server_name),
        transport: trim(f.transport),
        endpoint: trim(f.endpoint),
        notes: trim(f.notes) || undefined,
      };
    case "metrics_platform":
      return {
        provider: trim(f.provider),
        entity_key_field: trim(f.entity_key_field),
        grain: trim(f.grain),
        freshness_sla_hours: trim(f.freshness_sla_hours) ? Number(trim(f.freshness_sla_hours)) : undefined,
        taxonomy_ref: trim(f.taxonomy_ref) || undefined,
        notes: trim(f.notes) || undefined,
      };
    default:
      return {};
  }
}

export function summarizeConnection(row: ResourceConfig): string {
  const c = row.connection_config ?? {};
  switch (row.type) {
    case "mcp": {
      const parts = [c.server_name, c.transport, c.endpoint].filter(Boolean).map(String);
      return parts.join(" · ") || "—";
    }
    case "metrics_platform":
      return [c.provider, c.grain].filter(Boolean).join(" · ") || "—";
    case "file_store": {
      const fileId = fileIdFromConfig(c);
      const fileName = fileNameFromConfig(c);
      if (fileName && fileId) return `${fileName} · ${fileId}`;
      if (fileId) return fileId;
      if (typeof c.notes === "string" && c.notes.trim()) return c.notes.trim();
      return "文件库 · 用途见条目说明";
    }
    default:
      break;
  }
  try {
    const s = JSON.stringify(c);
    return s.length > 120 ? `${s.slice(0, 120)}…` : s || "—";
  } catch {
    return "—";
  }
}
