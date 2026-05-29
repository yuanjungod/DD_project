import { useCallback, useEffect, useMemo } from "react";
import {
  Background,
  Connection,
  Controls,
  Handle,
  MiniMap,
  NodeResizer,
  Node,
  NodeProps,
  Position,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  applyEdgeChanges,
  useEdgesState,
  useNodesState,
  type Edge,
  type EdgeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  createGraphNodeId,
  inferEntryAndReportNodes,
  normalizeWorkflowGraph,
  resolveGraphExecutionLevels,
  resolveGraphLayoutLevels,
} from "../domain/workflowGraph";
import type { AgentTemplate, WorkflowGraph } from "../types/domain";

type AgentIntro = {
  role: string;
  summary: string;
  meta: string;
};

function truncateText(text: string, maxLen = 140): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "";
  }
  if (normalized.length <= maxLen) {
    return normalized;
  }
  return `${normalized.slice(0, maxLen)}…`;
}

function agentIntro(agent: AgentTemplate | undefined): AgentIntro {
  if (!agent) {
    return { role: "", summary: "", meta: "" };
  }

  const summary = truncateText(agent.prompt || agent.role || "");
  const metaParts: string[] = [];
  if (agent.skill_package_ids.length > 0) {
    metaParts.push(`${agent.skill_package_ids.length} 技能`);
  }
  if (agent.resource_ids.length > 0) {
    metaParts.push(`${agent.resource_ids.length} 资源`);
  }

  return {
    role: agent.role.trim(),
    summary,
    meta: metaParts.join(" · "),
  };
}

function AgentIntroBlock({ intro, className }: { intro: AgentIntro; className?: string }) {
  if (!intro.role && !intro.summary && !intro.meta) {
    return null;
  }

  return (
    <div className={className ?? "workflow-agent-intro"}>
      {intro.role ? <p className="workflow-agent-intro__role">{intro.role}</p> : null}
      {intro.summary ? <p className="workflow-agent-intro__summary">{intro.summary}</p> : null}
      {intro.meta ? <p className="workflow-agent-intro__meta">{intro.meta}</p> : null}
    </div>
  );
}

type AgentNodeData = {
  label: string;
  agentId: string;
  intro: AgentIntro;
  missingAgent: boolean;
  onAgentChange: (nodeId: string, agentId: string) => void;
  onRemove: (nodeId: string) => void;
  onResize: (nodeId: string, width: number, height: number) => void;
};

type AgentFlowNode = Node<AgentNodeData, "agentNode">;

const DEFAULT_NODE_WIDTH = 240;
const DEFAULT_NODE_HEIGHT = 168;
const MIN_NODE_WIDTH = 200;
const MIN_NODE_HEIGHT = 120;
const MAX_NODE_WIDTH = 420;
const MAX_NODE_HEIGHT = 360;

const edgeDefaults = {
  type: "smoothstep" as const,
  animated: true,
  deletable: true,
  selectable: true,
  focusable: true,
  markerEnd: {
    type: MarkerType.ArrowClosed,
    width: 18,
    height: 18,
    color: "#2563eb",
  },
  style: { stroke: "#2563eb", strokeWidth: 2 },
};

function AgentNode({ id, data, selected }: NodeProps<AgentFlowNode>) {
  return (
    <>
      <NodeResizer
        isVisible={selected}
        minWidth={MIN_NODE_WIDTH}
        minHeight={MIN_NODE_HEIGHT}
        maxWidth={MAX_NODE_WIDTH}
        maxHeight={MAX_NODE_HEIGHT}
        lineClassName="workflow-graph-node__resize-line"
        handleClassName="workflow-graph-node__resize-handle"
        onResizeEnd={(_event, params) => {
          data.onResize(id, Math.round(params.width), Math.round(params.height));
        }}
      />
      <div className={`workflow-graph-node ${data.missingAgent ? "is-missing" : ""}`}>
        <Handle
          type="target"
          position={Position.Left}
          id="in"
          className="workflow-graph-node__handle workflow-graph-node__handle--in"
        />
        <div className="workflow-graph-node__body">
          <AgentIntroBlock intro={data.intro} className="workflow-graph-node__intro" />
          <div className="workflow-graph-node__title">{data.label || "未选择 Agent"}</div>
          {data.agentId ? <code className="workflow-graph-node__id">{data.agentId}</code> : null}
        </div>
        <button type="button" className="workflow-graph-node__remove" onClick={() => data.onRemove(id)}>
          移除
        </button>
        <Handle
          type="source"
          position={Position.Right}
          id="out"
          className="workflow-graph-node__handle workflow-graph-node__handle--out"
        />
      </div>
    </>
  );
}

const nodeTypes = { agentNode: AgentNode };

function layoutPositions(graph: WorkflowGraph): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  for (const node of graph.nodes) {
    if (node.position) {
      positions.set(node.id, node.position);
    }
  }

  let levels: string[][] = [];
  try {
    levels = resolveGraphLayoutLevels(graph);
  } catch {
    levels = graph.nodes.map((node) => [node.id]);
  }

  const xGap = 280;
  const yGap = 180;
  for (let levelIndex = 0; levelIndex < levels.length; levelIndex += 1) {
    const row = levels[levelIndex];
    const columnHeight = (row.length - 1) * yGap;
    for (let columnIndex = 0; columnIndex < row.length; columnIndex += 1) {
      const nodeId = row[columnIndex];
      if (!positions.has(nodeId)) {
        positions.set(nodeId, {
          x: levelIndex * xGap + 40,
          y: columnIndex * yGap - columnHeight / 2 + 80,
        });
      }
    }
  }
  return positions;
}

function nodeDimensions(node: WorkflowGraph["nodes"][number]): { width: number; height: number } {
  return {
    width: node.width && node.width >= MIN_NODE_WIDTH ? node.width : DEFAULT_NODE_WIDTH,
    height: node.height && node.height >= MIN_NODE_HEIGHT ? node.height : DEFAULT_NODE_HEIGHT,
  };
}

function readFlowNodeSize(flowNode: AgentFlowNode | undefined): { width?: number; height?: number } {
  if (!flowNode) {
    return {};
  }
  const width =
    typeof flowNode.width === "number"
      ? flowNode.width
      : typeof flowNode.style?.width === "number"
        ? flowNode.style.width
        : flowNode.measured?.width;
  const height =
    typeof flowNode.height === "number"
      ? flowNode.height
      : typeof flowNode.style?.height === "number"
        ? flowNode.style.height
        : flowNode.measured?.height;
  return {
    width: typeof width === "number" ? Math.round(width) : undefined,
    height: typeof height === "number" ? Math.round(height) : undefined,
  };
}

function graphToFlow(
  graph: WorkflowGraph,
  agentById: Map<string, AgentTemplate>,
  callbacks: Pick<AgentNodeData, "onAgentChange" | "onRemove" | "onResize">,
): { nodes: AgentFlowNode[]; edges: Edge[] } {
  const positions = layoutPositions(graph);
  const nodes: AgentFlowNode[] = graph.nodes.map((node) => {
    const agent = agentById.get(node.agent_template_id);
    const missingAgent = Boolean(node.agent_template_id && !agent);
    const intro = agentIntro(agent);
    const { width, height } = nodeDimensions(node);
    return {
      id: node.id,
      type: "agentNode",
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      style: { width, height },
      data: {
        label: agent?.name || node.agent_template_id || "未选择 Agent",
        agentId: node.agent_template_id,
        intro,
        missingAgent,
        onAgentChange: callbacks.onAgentChange,
        onRemove: callbacks.onRemove,
        onResize: callbacks.onResize,
      },
    };
  });

  const edges: Edge[] = (graph.edges ?? []).map((edge) => ({
    id: `${edge.from}->${edge.to}`,
    source: edge.from,
    target: edge.to,
    sourceHandle: "out",
    targetHandle: "in",
    ...edgeDefaults,
    className: "workflow-graph-edge",
  }));

  return { nodes, edges };
}

function flowToGraph(nodes: AgentFlowNode[], edges: Edge[], previous: WorkflowGraph): WorkflowGraph {
  const flowById = new Map(nodes.map((node) => [node.id, node]));
  const nextGraph: WorkflowGraph = {
    ...previous,
    nodes: previous.nodes.map((node) => {
      const flowNode = flowById.get(node.id);
      const size = readFlowNodeSize(flowNode);
      return {
        ...node,
        position: flowNode?.position ?? node.position,
        width: size.width ?? node.width,
        height: size.height ?? node.height,
      };
    }),
    edges: edges.map((edge) => ({ from: edge.source, to: edge.target })),
  };
  const { entryNode, reportNode } = inferEntryAndReportNodes(nextGraph);
  nextGraph.entry_node = entryNode;
  nextGraph.report_node = reportNode;
  return nextGraph;
}

type WorkflowGraphEditorInnerProps = {
  graph: WorkflowGraph;
  agents: AgentTemplate[];
  onChange: (graph: WorkflowGraph) => void;
};

function WorkflowGraphEditorInner({ graph, agents, onChange }: WorkflowGraphEditorInnerProps) {
  const agentById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);
  const selectableAgents = useMemo(() => agents.filter((agent) => agent.enabled), [agents]);

  const handleAgentChange = useCallback(
    (nodeId: string, agentId: string) => {
      onChange(
        normalizeWorkflowGraph({
          ...graph,
          nodes: graph.nodes.map((node) =>
            node.id === nodeId ? { ...node, agent_template_id: agentId } : node,
          ),
        }),
      );
    },
    [graph, onChange],
  );

  const handleRemoveNode = useCallback(
    (nodeId: string) => {
      onChange(
        normalizeWorkflowGraph({
          ...graph,
          nodes: graph.nodes.filter((node) => node.id !== nodeId),
          edges: graph.edges.filter((edge) => edge.from !== nodeId && edge.to !== nodeId),
        }),
      );
    },
    [graph, onChange],
  );

  const handleResizeNode = useCallback(
    (nodeId: string, width: number, height: number) => {
      onChange(
        normalizeWorkflowGraph({
          ...graph,
          nodes: graph.nodes.map((node) =>
            node.id === nodeId ? { ...node, width, height } : node,
          ),
        }),
      );
    },
    [graph, onChange],
  );

  const flowSeed = useMemo(
    () =>
      graphToFlow(graph, agentById, {
        onAgentChange: handleAgentChange,
        onRemove: handleRemoveNode,
        onResize: handleResizeNode,
      }),
    [graph, agentById, handleAgentChange, handleRemoveNode, handleResizeNode],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<AgentFlowNode>(flowSeed.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(flowSeed.edges);

  useEffect(() => {
    setNodes(flowSeed.nodes);
    setEdges(flowSeed.edges);
  }, [flowSeed, setEdges, setNodes]);

  const syncGraph = useCallback(
    (nextNodes: AgentFlowNode[], nextEdges: Edge[]) => {
      onChange(flowToGraph(nextNodes, nextEdges, graph));
    },
    [graph, onChange],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<Edge>[]) => {
      const nextEdges = applyEdgeChanges(changes, edges);
      onEdgesChange(changes);
      if (changes.some((change) => change.type === "remove")) {
        syncGraph(nodes, nextEdges);
      }
    },
    [edges, nodes, onEdgesChange, syncGraph],
  );

  const onEdgeDoubleClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      const nextEdges = edges.filter((item) => item.id !== edge.id);
      setEdges(nextEdges);
      syncGraph(nodes, nextEdges);
    },
    [edges, nodes, setEdges, syncGraph],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target || connection.source === connection.target) {
        return;
      }
      const exists = graph.edges.some(
        (edge) => edge.from === connection.source && edge.to === connection.target,
      );
      if (exists) {
        return;
      }
      const nextGraph = normalizeWorkflowGraph({
        ...graph,
        edges: [...graph.edges, { from: connection.source, to: connection.target }],
      });
      onChange(nextGraph);
    },
    [graph, onChange],
  );

  const onNodeDragStop = useCallback(
    (_event: React.MouseEvent, node: AgentFlowNode) => {
      syncGraph(
        nodes.map((item) => (item.id === node.id ? { ...item, position: node.position } : item)),
        edges,
      );
    },
    [edges, nodes, syncGraph],
  );

  function addAgentNode(agentId: string) {
    const nodeId = createGraphNodeId(graph);
    const nextGraph = normalizeWorkflowGraph({
      ...graph,
      nodes: [
        ...graph.nodes,
        {
          id: nodeId,
          agent_template_id: agentId,
          position: { x: 120, y: graph.nodes.length * 120 + 40 },
          width: DEFAULT_NODE_WIDTH,
          height: DEFAULT_NODE_HEIGHT,
        },
      ],
    });
    onChange(nextGraph);
  }


  let parallelHint = "";
  try {
    const levels = resolveGraphExecutionLevels(graph);
    parallelHint = levels.map((level) => level.join(" · ")).join("  →  ");
  } catch {
    parallelHint = "当前连线存在环，请调整后再保存。";
  }

  return (
    <div className="workflow-graph-editor">
      <aside className="workflow-graph-editor__palette">
        <div className="workflow-graph-editor__palette-head">
          <h3 className="form-section__title">Agent 节点</h3>
          <p className="muted">点击添加到画布；选中节点后可拖拽边角调整大小；从右侧拖线到左侧表示依赖；选中连线后 Delete 删除，或双击连线。</p>
        </div>
        {selectableAgents.length === 0 ? (
          <p className="workflow-graph-editor__empty">暂无可用 Agent，请先在「Agent 配置」中创建并启用。</p>
        ) : (
          <ul className="workflow-graph-editor__agent-list">
            {selectableAgents.map((agent) => {
              const intro = agentIntro(agent);
              return (
                <li key={agent.id}>
                  <button type="button" className="workflow-graph-editor__agent-button" onClick={() => addAgentNode(agent.id)}>
                    <AgentIntroBlock intro={intro} className="workflow-graph-editor__agent-intro" />
                    <strong>{agent.name || "未命名 Agent"}</strong>
                    {agent.role ? <span className="muted">{agent.role}</span> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      <div className="workflow-graph-editor__canvas-wrap">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={edgeDefaults}
          onNodesChange={onNodesChange}
          onEdgesChange={handleEdgesChange}
          onEdgeDoubleClick={onEdgeDoubleClick}
          deleteKeyCode={["Backspace", "Delete"]}
          onConnect={onConnect}
          onNodeDragStop={onNodeDragStop}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={18} size={1} />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
        <p className="workflow-graph-editor__levels muted">
          执行层级（同层并行）：{parallelHint || "请添加节点"}
        </p>
      </div>
    </div>
  );
}

export type WorkflowGraphEditorProps = {
  graph: WorkflowGraph;
  agents: AgentTemplate[];
  onChange: (graph: WorkflowGraph) => void;
};

export function WorkflowGraphEditor(props: WorkflowGraphEditorProps) {
  return (
    <ReactFlowProvider>
      <WorkflowGraphEditorInner {...props} />
    </ReactFlowProvider>
  );
}
