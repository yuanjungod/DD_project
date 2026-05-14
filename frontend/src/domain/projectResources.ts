/** Shared project-resource type labels and form parsing (create flow + persisted panel). */

export type ProjectResourceType =
  | "trusted_source"
  | "blocked_source"
  | "competitor"
  | "file_reference"
  | "external_clue"
  | "metric"
  | "agent_resource_scope";

export const PROJECT_RESOURCE_TYPE_LABELS: Record<ProjectResourceType, string> = {
  trusted_source: "可信来源 URL / 描述",
  blocked_source: "屏蔽来源",
  competitor: "竞争对手",
  file_reference: "已上传文件引用",
  external_clue: "外部线索摘要",
  metric: "财务/业务指标定义",
  agent_resource_scope: "Agent 资源作用域",
};

export type ParsedProjectResource = {
  type: ProjectResourceType;
  value: string;
  metadata_json: Record<string, unknown>;
};

export function emptyFieldsForResourceType(type: ProjectResourceType): Record<string, string> {
  switch (type) {
    case "trusted_source":
      return { value: "", label: "", notes: "" };
    case "blocked_source":
      return { value: "", notes: "" };
    case "competitor":
      return { value: "", website: "", ticker: "", notes: "" };
    case "file_reference":
      return { value: "", label: "", notes: "" };
    case "external_clue":
      return { summary: "", category: "", priority: "normal", source_label: "", notes: "" };
    case "metric":
      return {
        code: "",
        name: "",
        unit: "",
        description: "",
        category: "general",
        source_type: "manual",
        source_ref: "",
        target_direction: "unspecified",
        threshold_op: "",
        threshold_value: "",
        frequency: "",
        baseline_value: "",
        notes: "",
      };
    case "agent_resource_scope":
      return { agent_id: "", uploaded_file_ids: "", notes: "" };
    default:
      return { value: "" };
  }
}

/** Returns null if validation fails (empty primary value). */
export function parseProjectResourceForm(
  rtype: ProjectResourceType,
  fields: Record<string, string>,
): ParsedProjectResource | null {
  const metadata: Record<string, unknown> = {};
  let value = "";

  if (rtype === "trusted_source") {
    value = fields.value?.trim() ?? "";
    metadata.label = fields.label?.trim() || "";
    metadata.notes = fields.notes?.trim() || "";
  } else if (rtype === "blocked_source") {
    value = fields.value?.trim() ?? "";
    metadata.notes = fields.notes?.trim() || "";
  } else if (rtype === "competitor") {
    value = fields.value?.trim() ?? "";
    metadata.website = fields.website?.trim() || "";
    metadata.ticker = fields.ticker?.trim() || "";
    metadata.notes = fields.notes?.trim() || "";
  } else if (rtype === "file_reference") {
    value = fields.value?.trim() ?? "";
    metadata.label = fields.label?.trim() || "";
    metadata.notes = fields.notes?.trim() || "";
  } else if (rtype === "external_clue") {
    value = fields.summary?.trim() ?? "";
    metadata.category = fields.category?.trim() || "";
    metadata.priority = fields.priority?.trim() || "normal";
    metadata.source_label = fields.source_label?.trim() || "";
    metadata.notes = fields.notes?.trim() || "";
  } else if (rtype === "metric") {
    value = fields.code?.trim() ?? "";
    const thOp = fields.threshold_op?.trim();
    const thVal = fields.threshold_value?.trim();
    if (thOp && thVal) {
      metadata.threshold = { op: thOp, value: thVal };
    }
    metadata.name = fields.name?.trim() || value;
    metadata.unit = fields.unit?.trim() || "";
    metadata.description = fields.description?.trim() || "";
    metadata.category = fields.category?.trim() || "general";
    metadata.source_type = fields.source_type?.trim() || "manual";
    metadata.source_ref = fields.source_ref?.trim() || "";
    metadata.target_direction = fields.target_direction?.trim() || "unspecified";
    metadata.frequency = fields.frequency?.trim() || "";
    metadata.baseline_value = fields.baseline_value?.trim() || "";
    metadata.notes = fields.notes?.trim() || "";
  } else if (rtype === "agent_resource_scope") {
    value = fields.agent_id?.trim() ?? "";
    metadata.uploaded_file_ids = (fields.uploaded_file_ids ?? "")
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
    metadata.notes = fields.notes?.trim() || "";
  }

  if (!value) return null;
  return { type: rtype, value, metadata_json: metadata };
}

export function headlineForResourceRow(row: {
  type: string;
  value: string;
  metadata_json?: Record<string, unknown>;
}): string {
  const meta = row.metadata_json ?? {};
  if (row.type === "metric") {
    const nm = typeof meta.name === "string" ? meta.name : "";
    return `${row.value}${nm ? ` · ${nm}` : ""}`;
  }
  if (row.type === "competitor" && typeof meta.website === "string" && meta.website) {
    return `${row.value} · ${meta.website}`;
  }
  if (row.type === "external_clue" && typeof meta.category === "string" && meta.category) {
    const head = row.value.length > 80 ? `${row.value.slice(0, 80)}…` : row.value;
    return `${head} · ${meta.category}`;
  }
  if (row.type === "file_reference") {
    const fn = typeof meta.original_filename === "string" ? meta.original_filename.trim() : "";
    const lbl = typeof meta.label === "string" ? meta.label.trim() : "";
    if (fn) return fn;
    if (lbl) return `${lbl} · ${row.value}`;
  }
  if (row.type === "agent_resource_scope") {
    const fileIds = Array.isArray(meta.uploaded_file_ids) ? meta.uploaded_file_ids.length : 0;
    return `${row.value}${fileIds ? ` · ${fileIds} 个 file_id` : ""}`;
  }
  return row.value.length > 120 ? `${row.value.slice(0, 120)}…` : row.value;
}
