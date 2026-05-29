/** Rules for filesystem-safe technical identifiers (agent/workflow/skill/resource ids). */

export const TECHNICAL_ID_PATTERN = /^[a-zA-Z0-9_-]+$/;

export const TECHNICAL_ID_PLACEHOLDER = "留空自动生成；仅英文、数字、-、_";

export const TECHNICAL_ID_HINT =
  "技术 ID 会写入文件夹路径和 API，只支持英文、数字、连字符和下划线。中文展示名请填在「名称」。";

export function normalizeOptionalTechnicalId(raw: string): string | undefined {
  const text = raw.trim();
  if (!text) return undefined;
  return TECHNICAL_ID_PATTERN.test(text) ? text : undefined;
}

export function technicalIdValidationError(raw: string): string | null {
  const text = raw.trim();
  if (!text || TECHNICAL_ID_PATTERN.test(text)) return null;
  return `${TECHNICAL_ID_HINT} 当前输入将被拒绝，请修改或留空。`;
}
