import type { WorkflowGraph } from "../types/domain";

export class WorkflowGraphValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkflowGraphValidationError";
  }
}

function graphNodes(graph: WorkflowGraph | null | undefined): WorkflowGraph["nodes"] {
  return (graph?.nodes ?? []).filter((node) => Boolean(node.id));
}

function buildAdjacency(graph: WorkflowGraph) {
  const nodes = graphNodes(graph);
  const byNodeId = new Map(nodes.map((node) => [node.id, node]));
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();

  for (const node of nodes) {
    incoming.set(node.id, []);
    outgoing.set(node.id, []);
  }

  for (const edge of graph.edges ?? []) {
    const source = edge.from?.trim();
    const target = edge.to?.trim();
    if (!source || !target) {
      continue;
    }
    if (!byNodeId.has(source) || !byNodeId.has(target)) {
      throw new WorkflowGraphValidationError(`Edge references unknown node: ${source} -> ${target}`);
    }
    outgoing.get(source)?.push(target);
    incoming.get(target)?.push(source);
  }

  for (const node of nodes) {
    outgoing.get(node.id)?.sort();
    incoming.get(node.id)?.sort();
  }

  return { byNodeId, incoming, outgoing };
}

function executionLevels(graph: WorkflowGraph, validateAgents: boolean): string[][] {
  const nodes = graphNodes(graph);
  if (nodes.length === 0) {
    throw new WorkflowGraphValidationError("Workflow graph must include at least one node");
  }
  if (validateAgents) {
    for (const node of nodes) {
      if (!node.agent_template_id?.trim()) {
        throw new WorkflowGraphValidationError(`Graph node ${node.id} is missing agent_template_id`);
      }
    }
  }

  const { byNodeId, incoming, outgoing } = buildAdjacency(graph);
  const inDegree = new Map<string, number>();
  for (const nodeId of byNodeId.keys()) {
    inDegree.set(nodeId, incoming.get(nodeId)?.length ?? 0);
  }

  const levels: string[][] = [];
  let current = [...byNodeId.keys()].filter((nodeId) => (inDegree.get(nodeId) ?? 0) === 0).sort();

  while (current.length > 0) {
    levels.push(current);
    const nextLevel: string[] = [];
    for (const nodeId of current) {
      for (const target of outgoing.get(nodeId) ?? []) {
        const next = (inDegree.get(target) ?? 0) - 1;
        inDegree.set(target, next);
        if (next === 0) {
          nextLevel.push(target);
        }
      }
    }
    current = nextLevel.sort();
  }

  if (levels.flat().length !== byNodeId.size) {
    throw new WorkflowGraphValidationError("Workflow graph contains a cycle");
  }
  return levels;
}

export function validateWorkflowGraph(graph: WorkflowGraph): void {
  executionLevels(graph, true);
}

export function resolveGraphExecutionLevels(graph: WorkflowGraph): string[][] {
  return executionLevels(graph, true);
}

export function resolveGraphLayoutLevels(graph: WorkflowGraph): string[][] {
  return executionLevels(graph, false);
}

function collectNodeAgentIds(node: { agent_template_id?: string; sub_agent_template_ids?: string[] }): string[] {
  const ids: string[] = [];
  const masterId = node.agent_template_id?.trim();
  if (masterId) {
    ids.push(masterId);
  }
  for (const subAgentId of node.sub_agent_template_ids ?? []) {
    const sub = (subAgentId ?? "").trim();
    if (sub) {
      ids.push(sub);
    }
  }
  return ids;
}

/** Matches `shared/workflow_graph.resolve_graph_node_ids` (topological order; agents optional). */
export function resolveGraphNodeIds(graph: WorkflowGraph | null | undefined): string[] {
  if (!graph || graphNodes(graph).length === 0) {
    return [];
  }
  try {
    return resolveGraphLayoutLevels(graph).flat();
  } catch {
    return [];
  }
}

/** Matches `shared/workflow_graph.resolve_graph_agent_order`. */
export function resolveGraphAgentOrder(graph: WorkflowGraph | null | undefined): string[] {
  const nodes = graphNodes(graph);
  if (nodes.length === 0) {
    return [];
  }

  const byNodeId = new Map(nodes.map((node) => [node.id, node]));
  const agentIds: string[] = [];

  for (const nodeId of resolveGraphNodeIds(graph)) {
    const node = byNodeId.get(nodeId);
    if (node) {
      agentIds.push(...collectNodeAgentIds(node));
    }
  }

  return agentIds;
}

export function inferEntryAndReportNodes(graph: WorkflowGraph): { entryNode: string; reportNode: string } {
  const { byNodeId, incoming, outgoing } = buildAdjacency(graph);
  if (byNodeId.size === 0) {
    return { entryNode: "", reportNode: "" };
  }

  const explicitEntry = graph.entry_node?.trim() ?? "";
  const explicitReport = graph.report_node?.trim() ?? "";
  const roots = [...byNodeId.keys()].filter((nodeId) => (incoming.get(nodeId)?.length ?? 0) === 0).sort();
  const sinks = [...byNodeId.keys()].filter((nodeId) => (outgoing.get(nodeId)?.length ?? 0) === 0).sort();
  const firstNode = [...byNodeId.keys()][0] ?? "";

  return {
    entryNode: byNodeId.has(explicitEntry) ? explicitEntry : roots[0] ?? firstNode,
    reportNode: byNodeId.has(explicitReport) ? explicitReport : sinks[sinks.length - 1] ?? firstNode,
  };
}

export function createEmptyWorkflowGraph(): WorkflowGraph {
  return {
    nodes: [],
    edges: [],
    entry_node: "",
    report_node: "",
  };
}

export function createGraphNodeId(existing: WorkflowGraph): string {
  const used = new Set((existing.nodes ?? []).map((node) => node.id));
  let index = (existing.nodes?.length ?? 0) + 1;
  let candidate = `node_${String(index).padStart(2, "0")}`;
  while (used.has(candidate)) {
    index += 1;
    candidate = `node_${String(index).padStart(2, "0")}`;
  }
  return candidate;
}

export function normalizeWorkflowGraph(graph: WorkflowGraph): WorkflowGraph {
  const { entryNode, reportNode } = inferEntryAndReportNodes(graph);
  return {
    ...graph,
    nodes: graph.nodes ?? [],
    edges: graph.edges ?? [],
    entry_node: entryNode,
    report_node: reportNode,
  };
}
