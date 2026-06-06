import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent } from "react";
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

interface CursorPosition {
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
  const [cursorPosition, setCursorPosition] = useState<CursorPosition>();
  const [zoom, setZoom] = useState(1);
  const frameRef = useRef<number | undefined>(undefined);
  const pendingCursorRef = useRef<CursorPosition | undefined>(undefined);
  const width = 1280;
  const height = 780;
  const positions = useMemo<Map<string, NodePosition>>(() => {
    return graph ? buildPositions(graph.nodes, graph.seed_id, width, height) : new Map<string, NodePosition>();
  }, [graph]);
  const displayedPositions = useMemo(() => {
    return cursorPosition ? displacePositions(positions, cursorPosition) : positions;
  }, [cursorPosition, positions]);

  useEffect(() => {
    return () => {
      if (frameRef.current !== undefined) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const svgX = ((event.clientX - rect.left) / rect.width) * width;
    const svgY = ((event.clientY - rect.top) / rect.height) * height;
    pendingCursorRef.current = {
      x: width / 2 + (svgX - width / 2) / zoom,
      y: height / 2 + (svgY - height / 2) / zoom
    };
    if (frameRef.current !== undefined) {
      return;
    }
    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = undefined;
      setCursorPosition(pendingCursorRef.current);
    });
  }

  function handlePointerLeave() {
    pendingCursorRef.current = undefined;
    setCursorPosition(undefined);
    setHoveredNodeId(undefined);
  }

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
      <svg
        className="memory-canvas"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Focused graph neighborhood"
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
      >
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
            const from = displayedPositions.get(relationship.from_id);
            const to = displayedPositions.get(relationship.to_id);
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
            const position = displayedPositions.get(node.id);
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
                style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
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

function displacePositions(
  positions: Map<string, NodePosition>,
  cursor: CursorPosition
): Map<string, NodePosition> {
  const next = new Map<string, NodePosition>();
  positions.forEach((position, nodeId) => {
    const dx = position.x - cursor.x;
    const dy = position.y - cursor.y;
    const distance = Math.hypot(dx, dy);
    const radius = 190;
    if (distance > radius) {
      next.set(nodeId, position);
      return;
    }
    const strength = Math.pow(1 - distance / radius, 2);
    const safeDistance = Math.max(distance, 1);
    const unitX = dx / safeDistance;
    const unitY = dy / safeDistance;
    const phase = deterministicPhase(nodeId);
    const ripple = Math.sin(cursor.x * 0.014 + cursor.y * 0.011 + phase) * 0.45;
    const push = 11 * strength;
    const swirl = 5 * strength * ripple;
    next.set(nodeId, {
      x: position.x + unitX * push - unitY * swirl,
      y: position.y + unitY * push + unitX * swirl
    });
  });
  return next;
}

function deterministicPhase(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 997;
  }
  return hash / 997 * Math.PI * 2;
}
