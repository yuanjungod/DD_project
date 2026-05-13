export const workflowOptions = [
  {
    id: "standard_due_diligence",
    scenario: "standard",
    name: "标准完整尽调",
    focusAreas: ["业务", "财务", "法律", "股权", "舆情", "合规"],
  },
  {
    id: "legal_compliance_due_diligence",
    scenario: "legal_compliance",
    name: "法律合规重点尽调",
    focusAreas: ["法律", "合规", "诉讼", "行政处罚", "知识产权", "监管"],
  },
  {
    id: "financial_investment_due_diligence",
    scenario: "financial_investment",
    name: "财务投资重点尽调",
    focusAreas: ["财务", "融资", "经营质量", "商业模式", "行业位置"],
  },
  {
    id: "market_entry_due_diligence",
    scenario: "market_entry",
    name: "市场进入尽调",
    focusAreas: ["行业", "竞品", "产品", "市场声誉", "合作风险"],
  },
];

export function workflowName(workflowId?: string): string {
  return workflowOptions.find((workflow) => workflow.id === workflowId)?.name ?? "未配置流程";
}
