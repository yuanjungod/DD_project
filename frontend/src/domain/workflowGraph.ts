import type { WorkflowGraph } from "../types/domain";

/** Matches `shared/workflow_graph.resolve_graph_node_ids`. */
export function resolveGraphNodeIds(graph: WorkflowGraph | null | undefined): string[] {
  const nodes = graph?.nodes ?? [];
  if (nodes.length === 0) {
    return [];
  }

  const byNodeId = new Map(nodes.filter((node) => node.id).map((node) => [node.id, node]));
  const orderedNodeIds: string[] = [];
  let current = graph?.entry_node || nodes[0]?.id || "";
  const outgoing = new Map<string, string>();
  for (const edge of graph?.edges ?? []) {
    if (edge.from && edge.to) {
      outgoing.set(edge.from, edge.to);
    }
  }

  const seen = new Set<string>();
  while (current && byNodeId.has(current) && !seen.has(current)) {
    orderedNodeIds.push(current);
    seen.add(current);
    current = outgoing.get(current) ?? "";
  }

  for (const node of nodes) {
    if (node.id && !seen.has(node.id)) {
      orderedNodeIds.push(node.id);
    }
  }

  return orderedNodeIds;
}

/** Matches `shared/workflow_graph.resolve_graph_agent_order`. */
export function resolveGraphAgentOrder(graph: WorkflowGraph | null | undefined): string[] {
  const nodes = graph?.nodes ?? [];
  if (nodes.length === 0) {
    return [];
  }

  const byNodeId = new Map(nodes.filter((node) => node.id).map((node) => [node.id, node]));
  const agentIds: string[] = [];

  for (const nodeId of resolveGraphNodeIds(graph)) {
    const node = byNodeId.get(nodeId);
    const agentTemplateId = node?.agent_template_id?.trim();
    if (agentTemplateId) {
      agentIds.push(agentTemplateId);
    }
  }

  return agentIds;
}
