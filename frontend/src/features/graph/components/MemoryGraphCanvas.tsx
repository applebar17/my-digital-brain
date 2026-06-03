import { useMemo, useState } from "react";
import { EmptyState } from "../../../components/EmptyState";
import type { GraphViewNode, GraphViewResult } from "../../../types/graph";
import {
  graphNodeTone,
  graphRelationshipTone,
  graphToneColor,
  trimGraphLabel
} from "../utils/graphDisplay";

interface MemoryGraphCanvasProps {
  graph?: GraphViewResult;
  selectedNodeId?: string;
  isLoading: boolean;
  onSelectNode: (nodeId: string) => void;
}

interface NodePosition {
  x: number;
  y: number;
}

export function MemoryGraphCanvas({
  graph,
  selectedNodeId,
  isLoading,
  onSelectNode
}: MemoryGraphCanvasProps) {
  const [hoveredNodeId, setHoveredNodeId] = useState<string>();
  const [zoom, setZoom] = useState(1);
  const width = 1280;
  const height = 780;
  const positions = useMemo<Map<string, NodePosition>>(() => {
    return graph ? buildPositions(graph.nodes, graph.seed_id, width, height) : new Map<string, NodePosition>();
  }, [graph]);

  if (!graph) {
    return (
      <section className="memory-canvas-shell">
        <div className="memory-canvas-empty">
          <EmptyState title="No graph rendered" body="Select a seed node to enter the memory neighborhood." />
        </div>
      </section>
    );
  }

  return (
    <section className="memory-canvas-shell" aria-label="Memory graph canvas">
      <div className="memory-canvas-toolbar">
        <button type="button" onClick={() => setZoom((value) => Math.min(value + 0.1, 1.5))}>+</button>
        <button type="button" onClick={() => setZoom((value) => Math.max(value - 0.1, 0.72))}>-</button>
        <button type="button" onClick={() => setZoom(1)}>Fit</button>
      </div>
      <div className="memory-canvas-meta">
        <span>{graph.nodes.length} nodes</span>
        <span>{graph.relationships.length} edges</span>
        {isLoading && <span>Syncing</span>}
      </div>
      <svg className="memory-canvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Focused graph neighborhood">
        <defs>
          <filter id="nodeGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <g transform={`translate(${width / 2} ${height / 2}) scale(${zoom}) translate(${-width / 2} ${-height / 2})`}>
          {graph.relationships.map((relationship) => {
            const from = positions.get(relationship.from_id);
            const to = positions.get(relationship.to_id);
            if (!from || !to) {
              return null;
            }
            const active = hoveredNodeId === relationship.from_id || hoveredNodeId === relationship.to_id;
            const tone = graphRelationshipTone(relationship);
            return (
              <g className={`memory-edge ${active ? "is-active" : ""}`} key={relationship.id}>
                <line
                  className={`memory-edge-line memory-edge-${tone}`}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                />
                <text className="memory-edge-label" x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8}>
                  {trimGraphLabel(relationship.type, 18)}
                </text>
              </g>
            );
          })}

          {graph.nodes.map((node) => {
            const position = positions.get(node.id);
            if (!position) {
              return null;
            }
            const tone = graphNodeTone(node);
            const selected = selectedNodeId === node.id || graph.seed_id === node.id;
            const active = selected || hoveredNodeId === node.id;
            const color = graphToneColor(tone);
            return (
              <g
                className={`memory-node memory-node-${tone} ${active ? "is-active" : ""}`}
                key={node.id}
                role="button"
                tabIndex={0}
                transform={`translate(${position.x} ${position.y})`}
                onClick={() => onSelectNode(node.id)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(undefined)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    onSelectNode(node.id);
                  }
                }}
              >
                <g className="memory-node-shape">
                  <circle className="memory-node-halo" r={selected ? 28 : 22} style={{ stroke: color }} />
                  <circle className="memory-node-core" r={selected ? 9 : 7} style={{ fill: color, color }} />
                  <circle className="memory-node-pin" r="3" />
                  <foreignObject x="-78" y="16" width="156" height="44">
                    <div className="memory-node-label">
                      <strong>{trimGraphLabel(node.title ?? node.label)}</strong>
                      <span>{node.label}</span>
                    </div>
                  </foreignObject>
                </g>
              </g>
            );
          })}
        </g>
      </svg>
    </section>
  );
}

function buildPositions(
  nodes: GraphViewNode[],
  seedId: string,
  width: number,
  height: number
): Map<string, NodePosition> {
  const positions = new Map<string, NodePosition>();
  const centerX = width / 2;
  const centerY = height / 2;
  const neighbors = nodes.filter((node) => node.id !== seedId);

  positions.set(seedId, { x: centerX, y: centerY });
  neighbors.forEach((node, index) => {
    const ring = index % 2 === 0 ? 250 : 330;
    const angle = (index / Math.max(neighbors.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const jitter = index % 3 === 0 ? 38 : index % 3 === 1 ? -24 : 0;
    positions.set(node.id, {
      x: centerX + Math.cos(angle) * (ring + jitter),
      y: centerY + Math.sin(angle) * (ring - jitter * 0.4)
    });
  });

  return positions;
}
