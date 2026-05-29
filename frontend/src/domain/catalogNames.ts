/** User-facing catalog labels and duplicate name checks (IDs stay internal). */

export function normalizeCatalogName(name: string): string {
  return name.trim();
}

export function catalogDisplayName(item: { name?: string | null }, fallback = "未命名"): string {
  const text = normalizeCatalogName(item.name ?? "");
  return text || fallback;
}

export function findDuplicateCatalogName<T extends { id: string; name: string }>(
  items: T[],
  name: string,
  excludeId?: string | null,
): T | undefined {
  const key = normalizeCatalogName(name).toLowerCase();
  if (!key) return undefined;
  return items.find(
    (item) => item.id !== excludeId && normalizeCatalogName(item.name).toLowerCase() === key,
  );
}

export function duplicateCatalogNameError(kind: string, name: string, existing?: { name: string }): string | null {
  const trimmed = normalizeCatalogName(name);
  if (!trimmed) return `请填写${kind}名称。`;
  if (existing) return `${kind}名称「${trimmed}」已存在，请使用其他名称。`;
  return null;
}

export function slugFromCatalogName(name: string): string {
  const safe = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return safe || "item";
}
