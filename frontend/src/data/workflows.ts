import type { WorkflowTemplate } from "../types/domain";

const scenarioFocusAreas: Record<string, string[]> = {
  standard: ["业务", "财务", "法律", "股权", "舆情", "合规"],
  legal_compliance: ["法律", "合规", "诉讼", "行政处罚", "知识产权", "监管"],
  financial_investment: ["财务", "融资", "经营质量", "商业模式", "行业位置"],
  market_entry: ["行业", "竞品", "产品", "市场声誉", "合作风险"],
};

export function focusAreasForScenario(scenario: string): string[] {
  return scenarioFocusAreas[scenario] ?? ["业务", "财务", "法律", "合规"];
}

export function workflowName(workflowId?: string | null, templates: WorkflowTemplate[] = []): string {
  if (!workflowId) {
    return "未配置场景";
  }
  return templates.find((workflow) => workflow.id === workflowId)?.name ?? workflowId;
}
