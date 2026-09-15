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
  onClearSelection?: () => void;
}

interface NodePosition {
  x: number;
  y: number;
}

interface CursorPosition {
  x: number;
  y: number;
}

const LAYOUT_TWEEN_MS = 460;

export function MemoryGraphCanvas({
  graph,
  selectedNodeId,
  isLoading,
  onSelectNode,
  onClearSelection
}: MemoryGraphCanvasProps) {
  const [hoveredNodeId, setHoveredNodeId] = useState<string>();
  const [cursorPosition, setCursorPosition] = useState<CursorPosition>();
  const [zoom, setZoom] = useState(1);
  const frameRef = useRef<number | undefined>(undefined);
  const pendingCursorRef = useRef<CursorPosition | undefined>(undefined);
  const width = 1280;
  const height = 780;

  // A selection is a true focus: only the selected node, its direct neighbours,
  // and their connecting edges are rendered. The full graph remains in state.
  const focusMode = Boolean(
    graph && selectedNodeId && graph.nodes.some((node) => node.id === selectedNodeId)
  );
  const renderedGraph = useMemo(
    () => focusMode ? directNeighborhood(graph as GraphViewResult, selectedNodeId as string) : graph,
    [graph, focusMode, selectedNodeId]
  );

  const layout = useMemo<GraphLayout>(() => {
    if (!renderedGraph) {
      return { positions: new Map(), tierById: new Map() };
    }
    return focusMode
      ? buildFocusedLayout(renderedGraph, selectedNodeId as string, width, height)
      : {
          positions: buildPositions(renderedGraph.nodes, renderedGraph.seed_id, width, height),
          tierById: new Map()
        };
  }, [renderedGraph, focusMode, selectedNodeId]);

  const animatedPositions = useTweenedPositions(layout.positions);

  const displayedPositions = useMemo(() => {
    // The clean pyramid should not wobble under the cursor; only the radial view ripples.
    if (focusMode || !cursorPosition) {
      return animatedPositions;
    }
    return displacePositions(animatedPositions, cursorPosition);
  }, [animatedPositions, cursorPosition, focusMode]);

  useEffect(() => {
    return () => {
      if (frameRef.current !== undefined) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (focusMode) {
      return;
    }
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
  const graphToRender = renderedGraph as GraphViewResult;

  return (
    <section className="memory-canvas-shell" aria-label="Memory graph canvas">
      <div className="memory-canvas-toolbar">
        {focusMode && onClearSelection && (
          <button
            type="button"
            className="memory-canvas-back"
            onClick={() => onClearSelection()}
            aria-label="Exit focused node view"
          >
            ← Back
          </button>
        )}
        <button type="button" onClick={() => setZoom((value) => Math.min(value + 0.1, 1.5))}>+</button>
        <button type="button" onClick={() => setZoom((value) => Math.max(value - 0.1, 0.72))}>-</button>
        <button type="button" onClick={() => setZoom(1)}>Fit</button>
      </div>
      <div className="memory-canvas-meta">
        <span>{graphToRender.nodes.length} nodes</span>
        <span>{graphToRender.relationships.length} edges</span>
        {focusMode && <span>Focused view</span>}
        {isLoading && <span>Syncing</span>}
      </div>
      <svg
        className={`memory-canvas ${focusMode ? "is-focus" : ""}`}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Focused graph neighborhood"
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        onClick={() => {
          if (focusMode && onClearSelection) {
            onClearSelection();
          }
        }}
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
          {graphToRender.relationships.map((relationship) => {
            const from = displayedPositions.get(relationship.from_id);
            const to = displayedPositions.get(relationship.to_id);
            if (!from || !to) {
              return null;
            }
            const active = hoveredNodeId === relationship.from_id || hoveredNodeId === relationship.to_id;
            const touchesFocus =
              focusMode &&
              (relationship.from_id === selectedNodeId || relationship.to_id === selectedNodeId);
            const tone = graphRelationshipTone(relationship);
            return (
              <g
                className={`memory-edge ${active ? "is-active" : ""} ${
                  focusMode && touchesFocus ? "is-primary" : ""
                }`}
                key={relationship.id}
              >
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

          {graphToRender.nodes.map((node) => {
            const position = displayedPositions.get(node.id);
            if (!position) {
              return null;
            }
            const tone = graphNodeTone(node);
            const isSeed = focusMode ? selectedNodeId === node.id : graphToRender.seed_id === node.id;
            const selected = selectedNodeId === node.id || graphToRender.seed_id === node.id;
            const active = selected || hoveredNodeId === node.id;
            const color = graphToneColor(tone);
            const tier = layout.tierById.get(node.id);
            const tierClass = focusMode
              ? isSeed
                ? "is-seed"
                : `tier-${tier ?? 1}`
              : "";
            return (
              <g
                className={`memory-node memory-node-${tone} ${active ? "is-active" : ""} ${tierClass}`}
                key={node.id}
                role="button"
                tabIndex={0}
                style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectNode(node.id);
                }}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(undefined)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    onSelectNode(node.id);
                  }
                }}
              >
                <g className="memory-node-shape">
                  <circle className="memory-node-halo" r={isSeed ? 28 : 22} style={{ stroke: color }} />
                  <circle className="memory-node-core" r={isSeed ? 9 : 7} style={{ fill: color, color }} />
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

interface GraphLayout {
  positions: Map<string, NodePosition>;
  // Tier distance from the focused node (0 = focused). Absent for unreachable nodes.
  tierById: Map<string, number>;
}

/**
 * Animate a position map toward its latest target over a short tween, so both nodes
 * and their edge endpoints move together when the layout changes (radial <-> pyramid).
 */
function useTweenedPositions(target: Map<string, NodePosition>): Map<string, NodePosition> {
  const [positions, setPositions] = useState<Map<string, NodePosition>>(target);
  const latestRef = useRef<Map<string, NodePosition>>(target);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    latestRef.current = positions;
  }, [positions]);

  useEffect(() => {
    const from = latestRef.current;
    const start = performance.now();

    if (frameRef.current !== undefined) {
      window.cancelAnimationFrame(frameRef.current);
    }

    function step(now: number) {
      const progress = Math.min((now - start) / LAYOUT_TWEEN_MS, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = new Map<string, NodePosition>();
      target.forEach((destination, id) => {
        const origin = from.get(id) ?? destination;
        next.set(id, {
          x: origin.x + (destination.x - origin.x) * eased,
          y: origin.y + (destination.y - origin.y) * eased
        });
      });
      setPositions(next);
      if (progress < 1) {
        frameRef.current = window.requestAnimationFrame(step);
      } else {
        frameRef.current = undefined;
      }
    }

    frameRef.current = window.requestAnimationFrame(step);
    return () => {
      if (frameRef.current !== undefined) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
    // Re-run only when the target layout identity changes, not on every tween frame.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return positions;
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

function directNeighborhood(graph: GraphViewResult, focusId: string): GraphViewResult {
  const relationships = graph.relationships.filter(
    (relationship) => relationship.from_id === focusId || relationship.to_id === focusId
  );
  const nodeIds = new Set<string>([focusId]);
  relationships.forEach((relationship) => {
    nodeIds.add(relationship.from_id);
    nodeIds.add(relationship.to_id);
  });
  return {
    ...graph,
    seed_id: focusId,
    nodes: graph.nodes.filter((node) => nodeIds.has(node.id)),
    relationships
  };
}

/** The focused node sits above its direct neighbours in a compact, readable fan. */
function buildFocusedLayout(
  graph: GraphViewResult,
  focusId: string,
  width: number,
  height: number
): GraphLayout {
  const tierById = new Map<string, number>();
  tierById.set(focusId, 0);
  const centerX = width / 2;
  const positions = new Map<string, NodePosition>();
  positions.set(focusId, { x: centerX, y: 150 });
  const neighbours = graph.nodes.filter((node) => node.id !== focusId);
  const spanWidth = Math.min(width - 160, Math.max(180, neighbours.length * 150));
  neighbours.forEach((node, index) => {
    tierById.set(node.id, 1);
    positions.set(node.id, {
      x: neighbours.length <= 1
        ? centerX
        : centerX - spanWidth / 2 + (spanWidth * index) / (neighbours.length - 1),
      y: height * 0.58
    });
  });

  return { positions, tierById };
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
