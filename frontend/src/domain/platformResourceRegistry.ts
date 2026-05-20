/** 平台可用资源类型（磁盘 YAML），与「场景与Agent」里绑定哪些 ID 无关；本模块文案侧重条目登记含义。 */

export type PlatformResourceType =
  | "web"
  | "file_store"
  | "database"
  | "api"
  | "metrics_platform";

export const PLATFORM_RESOURCE_TYPE_OPTIONS: { id: PlatformResourceType; label: string; hint: string }[] = [
  {
    id: "web",
    label: "公开网页",
    hint: "登记对外网页资源的抓取范围与合规说明；此处只做目录化管理，不必填写工具参数。",
  },
  {
    id: "file_store",
    label: "文件库",
    hint: "上方维护平台共享文件的上传与删除；下方条目填写名称与用途说明即可（描述这批材料的用途）。",
  },
  {
    id: "database",
    label: "业务数据库",
    hint: "登记数据源概况（方言、密钥引用方式等），明文口令请勿写在此处；仅供说明与条目归档。",
  },
  {
    id: "api",
    label: "外部 API",
    hint: "登记可调用的外部接口概况（入口、认证方式占位等），便于查阅而非绑定某一工具实现。",
  },
  {
    id: "metrics_platform",
    label: "指标 / 数仓平台",
    hint: "登记指标/数仓资源概况（系统、粒度、口径文档链接等），用于条目管理与对齐说明。",
  },
];

export const KNOWN_PLATFORM_RESOURCE_TYPES = PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => o.id);

/** 「平台资源」页顶部标签（不含「全部」）；Agent 编排里勾选资源仍可使用含「全部」的 ResourceListFilter。 */
export type ResourceConfigsTabFilter = PlatformResourceType | "other" | "tools";

export type ResourceListFilter = ResourceConfigsTabFilter | "all";

/** 平台资源页一级标签：连接器资源类型 + 执行工具（只读目录）。 */
export const PLATFORM_CONFIG_TAB_OPTIONS: { id: ResourceConfigsTabFilter; label: string }[] = [
  ...PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => ({ id: o.id, label: o.label })),
  { id: "tools", label: "执行工具" },
];

export function isKnownPlatformResourceType(t: string): t is PlatformResourceType {
  return KNOWN_PLATFORM_RESOURCE_TYPES.includes(t as PlatformResourceType);
}

export function isToolsConfigTab(filter: string): filter is "tools" {
  return filter === "tools";
}

export function resourceListFilterLabel(filter: ResourceListFilter): string {
  if (filter === "all") return "全部类型";
  if (filter === "other") return "其他类型";
  if (filter === "tools") return "执行工具";
  return PLATFORM_RESOURCE_TYPE_OPTIONS.find((o) => o.id === filter)?.label ?? filter;
}
