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
    case "web":
      return {
        domains: "允许域名范围（每行一条，可含通配，可选）",
        rate_limit_rpm: "速率上限参考（请求/分钟，可选）",
        notes: "合规与抓取策略说明（可选）",
      };
    case "file_store":
      return {
        notes: "文件用途或策略说明（可选）",
      };
    case "database":
      return {
        dialect: "方言（postgres / mysql / …，可选登记）",
        secret_ref: "密钥引用 ID（勿写明文口令，可选登记）",
        schema: "默认 schema（可选）",
        notes: "权限与安全说明（可选）",
      };
    case "api":
      return {
        base_url: "Base URL（可选登记）",
        auth_type: "认证方式备注（bearer / api_key_header / none）",
        auth_header_name: "Header 名（若适用，可选）",
        notes: "环境与限流说明（可选）",
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
    case "web": {
      const domains = c.allowed_domains;
      const lines = Array.isArray(domains) ? domains.map((x) => String(x)).join("\n") : "";
      return {
        ...base,
        domains: lines,
        rate_limit_rpm: c.rate_limit_rpm != null ? String(c.rate_limit_rpm) : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    }
    case "file_store":
      return {
        ...base,
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "database":
      return {
        ...base,
        dialect: String(c.dialect ?? ""),
        secret_ref: String(c.secret_ref ?? ""),
        schema: typeof c.schema === "string" ? c.schema : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "api":
      return {
        ...base,
        base_url: String(c.base_url ?? ""),
        auth_type: typeof c.auth_type === "string" ? c.auth_type : "",
        auth_header_name: typeof c.auth_header_name === "string" ? c.auth_header_name : "",
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
    case "web": {
      const lines = (f.domains ?? "")
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      const out: Record<string, unknown> = { allowed_domains: lines };
      if (trim(f.rate_limit_rpm)) {
        const n = Number(trim(f.rate_limit_rpm));
        if (!Number.isNaN(n)) out.rate_limit_rpm = n;
      }
      if (trim(f.notes)) out.notes = trim(f.notes);
      return out;
    }
    case "file_store":
      return trim(f.notes) ? { notes: trim(f.notes) } : {};
    case "database":
      return {
        dialect: trim(f.dialect),
        secret_ref: trim(f.secret_ref),
        schema: trim(f.schema) || undefined,
        notes: trim(f.notes) || undefined,
      };
    case "api":
      return {
        base_url: trim(f.base_url),
        auth_type: trim(f.auth_type) || "none",
        auth_header_name: trim(f.auth_header_name) || undefined,
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
    case "web": {
      const d = c.allowed_domains;
      if (Array.isArray(d) && d.length) return `${d.length} 个域名`;
      break;
    }
    case "api":
      return String(c.base_url || "—");
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
