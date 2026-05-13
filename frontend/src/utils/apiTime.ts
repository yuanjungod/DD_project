/** Backend stores UTC; legacy JSON often omitted timezone, so JS treated it as local. */
export function formatApiDateTimeLocal(iso: string): string {
  const s = iso.trim();
  const hasExplicitTz = /[zZ]$|[+-]\d{2}:\d{2}$/.test(s);
  const normalized = hasExplicitTz ? s : `${s.slice(0, 19)}Z`;
  return new Date(normalized).toLocaleString();
}
