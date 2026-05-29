/** 平台可用资源类型（磁盘 YAML），与「Agent和场景」里绑定哪些 ID 无关；本模块文案侧重条目登记含义。 */

export type PlatformResourceType = "file_store" | "mcp" | "metrics_platform";

export const PLATFORM_RESOURCE_TYPE_OPTIONS: { id: PlatformResourceType; label: string; hint: string }[] = [
  {
    id: "file_store",
    label: "文件库",
    hint: "上方维护平台共享文件的上传与删除；下方条目填写名称与用途说明即可（描述这批材料的用途）。",
  },
  {
    id: "mcp",
    label: "MCP",
    hint: "登记 Model Context Protocol 服务连接信息（传输方式、端点或启动命令等），供 Agent 查阅与对齐。",
  },
  {
    id: "metrics_platform",
    label: "指标 / 数仓平台",
    hint: "登记指标/数仓资源概况（系统、粒度、口径文档链接等），用于条目管理与对齐说明。",
  },
];

export const KNOWN_PLATFORM_RESOURCE_TYPES = PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => o.id);

/** 「平台资源」页顶部标签（不含「全部」）；Agent 编排里勾选资源仍可使用含「全部」的 ResourceListFilter。 */
export type ResourceConfigsTabFilter = PlatformResourceType | "other";

export type ResourceListFilter = ResourceConfigsTabFilter | "all";

/** 平台资源页一级标签：连接器资源类型。 */
export const PLATFORM_CONFIG_TAB_OPTIONS: { id: ResourceConfigsTabFilter; label: string }[] =
  PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => ({ id: o.id, label: o.label }));

export function isKnownPlatformResourceType(t: string): t is PlatformResourceType {
  return KNOWN_PLATFORM_RESOURCE_TYPES.includes(t as PlatformResourceType);
}

export function resourceListFilterLabel(filter: ResourceListFilter): string {
  if (filter === "all") return "全部类型";
  if (filter === "other") return "其他类型";
  return PLATFORM_RESOURCE_TYPE_OPTIONS.find((o) => o.id === filter)?.label ?? filter;
}
