import type { WorkflowTemplate } from "../types/domain";

export { resolveGraphAgentOrder, resolveGraphNodeIds } from "../domain/workflowGraph";

export function workflowName(workflowId?: string | null, templates: WorkflowTemplate[] = []): string {
  if (!workflowId) {
    return "未配置场景";
  }
  return templates.find((workflow) => workflow.id === workflowId)?.name ?? workflowId;
}
