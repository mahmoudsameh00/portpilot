"use client";
// A pack decision run as a small static graph (Frontend plan §6.8, ADR-060 amendment 1 (c)): only the weekly_pack
// nodes the API lets through (`PACK_NODES` in pipelines/api/routers/packs.py), laid out once; the `node` events light
// the current step and keep the steps already passed. Nothing here can be dragged, zoomed or edited.
import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/base.css";

const LABEL: Record<string, string> = {
  insight_llm: "Insight agent",
  insight_tools: "Insight tools",
  insight_notes: "Insight notes",
  writer: "Writer",
  revise_failed: "Revise check",
  validator: "Validator",
  fallback: "Code fallback",
  approval: "Approval",
  publisher: "Publisher",
};

// three columns, read top-left to bottom-right, so the graph fits the decision panel (about 20 rem wide)
const POSITION: Record<string, { x: number; y: number }> = {
  insight_llm: { x: 0, y: 0 },
  insight_notes: { x: 130, y: 0 },
  writer: { x: 260, y: 0 },
  insight_tools: { x: 0, y: 70 },
  revise_failed: { x: 130, y: 70 },
  validator: { x: 260, y: 70 },
  fallback: { x: 130, y: 140 },
  approval: { x: 260, y: 140 },
  publisher: { x: 260, y: 210 },
};

// [source, target, side]: "r" = right → left (along a row), "b" = bottom → top (down a column)
const EDGES: [string, string, "r" | "b"][] = [
  ["insight_llm", "insight_tools", "b"],
  ["insight_llm", "insight_notes", "r"],
  ["insight_notes", "writer", "r"],
  ["writer", "validator", "b"],
  ["revise_failed", "validator", "r"],
  ["fallback", "validator", "r"],
  ["validator", "approval", "b"],
  ["approval", "publisher", "b"],
];

type StepData = { label: string; tone: string };

/** One step: its label in a box, four hidden handles so an edge leaves and enters on the side its layout needs. */
function Step({ data }: NodeProps<Node<StepData>>) {
  const hidden = "!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent";
  return (
    <div className={data.tone}>
      <Handle type="target" position={Position.Left} id="l" className={hidden} />
      <Handle type="target" position={Position.Top} id="t" className={hidden} />
      {data.label}
      <Handle type="source" position={Position.Right} id="r" className={hidden} />
      <Handle type="source" position={Position.Bottom} id="b" className={hidden} />
    </div>
  );
}
const NODE_TYPES = { step: Step };

export const PACK_GRAPH_NODES = Object.keys(LABEL);

export function RunGraph({ trace, running }: { trace: string[]; running: boolean }) {
  const passed = new Set(trace);
  const current = running ? trace.at(-1) : undefined;
  const nodes: Node<StepData>[] = PACK_GRAPH_NODES.map((id) => ({
    id,
    type: "step",
    position: POSITION[id]!,
    draggable: false,
    selectable: false,
    connectable: false,
    data: {
      label: LABEL[id]!,
      tone: [
        "rounded-md border px-1.5 py-1.5 text-center text-xs font-medium shadow-none",
        id === current
          ? "border-primary bg-primary text-primary-foreground"
          : passed.has(id)
            ? "border-primary bg-accent text-foreground"
            : "border-border bg-card text-muted-foreground",
      ].join(" "),
    },
    style: { width: 112 },
    ariaLabel: `${LABEL[id]}: ${id === current ? "working" : passed.has(id) ? "done" : "not run"}`,
  }));
  const edges: Edge[] = EDGES.map(([source, target, side]) => ({
    id: `${source}-${target}`,
    source,
    target,
    sourceHandle: side,
    targetHandle: side === "r" ? "l" : "t",
    type: "smoothstep",
    animated: source === current,
    style: {
      stroke: passed.has(source) && passed.has(target) ? "var(--primary)" : "var(--border)",
      strokeWidth: 1.5,
    },
  }));
  return (
    <figure className="flex flex-col gap-1.5">
      <div
        className="h-60 w-full overflow-hidden rounded-lg border bg-background"
        role="img"
        aria-label={`The pack's run: ${trace.length ? trace.map((n) => LABEL[n] ?? n).join(", then ") : "starting"}`}
        data-testid="run-graph"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.3}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} color="var(--border)" />
        </ReactFlow>
      </div>
      <figcaption className="text-xs text-muted-foreground">
        {current ? `Working: ${LABEL[current] ?? current}` : trace.length ? "Run finished" : "Starting…"}
      </figcaption>
    </figure>
  );
}
