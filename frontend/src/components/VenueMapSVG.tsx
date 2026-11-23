import { useEffect, useState } from "react";
import type { GraphNode, VenueGraphData } from "../types";
import { Navigation, Eye } from "lucide-react";

interface VenueMapSVGProps {
  venueId: string;
  junctionId: string;
  targetDestId: string;
  closedEdges?: [string, string][];
  taskId?: string;
}

export const VenueMapSVG: React.FC<VenueMapSVGProps> = ({
  venueId,
  junctionId,
  targetDestId,
  closedEdges = [],
  taskId,
}) => {
  const [graphData, setGraphData] = useState<VenueGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"svg" | "mpl">("svg");

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetch(`/api/venues/${venueId}/graph`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load venue graph");
        return res.json();
      })
      .then((data: VenueGraphData) => {
        if (isMounted) {
          setGraphData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Venue graph load error:", err);
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [venueId]);

  if (loading) {
    return (
      <div className="h-72 flex items-center justify-center bg-slate-50 border border-slate-200 rounded-lg">
        <div className="text-sm text-slate-500 animate-pulse flex items-center space-x-2">
          <Navigation className="w-4 h-4 animate-spin text-emerald-700" />
          <span>Computing topological graph layout...</span>
        </div>
      </div>
    );
  }

  if (!graphData) {
    return (
      <div className="h-72 flex items-center justify-center bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-500">
        Venue graph data unavailable.
      </div>
    );
  }

  // Node coordinate lookup
  const nodeMap = new Map<string, GraphNode>();
  graphData.nodes.forEach((n) => nodeMap.set(n.id, n));

  // Determine closed edge set (bidirectional)
  const isClosedEdge = (u: string, v: string) => {
    return closedEdges.some(
      ([a, b]) => (a === u && b === v) || (a === v && b === u)
    );
  };

  // Simple Breadth-First Shortest Path on non-closed edges
  const findPath = (start: string, end: string): string[] => {
    if (!start || !end || start === end) return [start];
    const queue: [string, string[]][] = [[start, [start]]];
    const visited = new Set<string>([start]);

    while (queue.length > 0) {
      const [curr, path] = queue.shift()!;
      if (curr === end) return path;

      const outgoing = graphData.edges
        .filter((e) => e.from_node === curr && !isClosedEdge(e.from_node, e.to_node))
        .map((e) => e.to_node);

      for (const nextNode of outgoing) {
        if (!visited.has(nextNode)) {
          visited.add(nextNode);
          queue.push([nextNode, [...path, nextNode]]);
        }
      }
    }
    return [];
  };

  const routePath = findPath(junctionId, targetDestId);
  const routeEdges = new Set<string>();
  for (let i = 0; i < routePath.length - 1; i++) {
    routeEdges.add(`${routePath[i]}->${routePath[i + 1]}`);
  }

  const firstHopKey =
    routePath.length >= 2 ? `${routePath[0]}->${routePath[1]}` : null;

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
        <div className="flex items-center space-x-2">
          <Navigation className="w-4 h-4 text-emerald-700" />
          <span className="font-semibold text-xs tracking-wider uppercase text-slate-700">
            Venue Topology: {graphData.name}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setViewMode(viewMode === "svg" ? "mpl" : "svg")}
            className="text-xs px-2.5 py-1 rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 transition-colors flex items-center space-x-1"
          >
            <Eye className="w-3 h-3 text-slate-500" />
            <span>{viewMode === "svg" ? "Show Matplotlib Plot" : "Show Interactive SVG"}</span>
          </button>
        </div>
      </div>

      {viewMode === "mpl" && taskId ? (
        <div className="p-3 flex justify-center bg-white">
          <img
            src={`/api/tasks/${taskId}/route-plot`}
            alt="Venue Route Plot"
            className="max-h-80 rounded border border-slate-200 object-contain"
          />
        </div>
      ) : (
        <div className="relative p-2 bg-slate-50/40">
          <svg viewBox="0 0 800 500" className="w-full h-auto max-h-80 select-none">
            <defs>
              <marker
                id="arrow-default"
                viewBox="0 0 10 10"
                refX="18"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#94a3b8" />
              </marker>
              <marker
                id="arrow-route"
                viewBox="0 0 10 10"
                refX="19"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#059669" />
              </marker>
              <marker
                id="arrow-first-hop"
                viewBox="0 0 10 10"
                refX="20"
                refY="5"
                markerWidth="8"
                markerHeight="8"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97706" />
              </marker>
            </defs>

            {/* Edges */}
            {graphData.edges.map((edge, idx) => {
              const u = nodeMap.get(edge.from_node);
              const v = nodeMap.get(edge.to_node);
              if (!u || !v) return null;

              const edgeKey = `${edge.from_node}->${edge.to_node}`;
              const isClosed = isClosedEdge(edge.from_node, edge.to_node);
              const isFirstHop = edgeKey === firstHopKey;
              const isRoute = routeEdges.has(edgeKey);

              let stroke = "#cbd5e1";
              let strokeWidth = 1.8;
              let strokeDash = undefined;
              let marker = "url(#arrow-default)";

              if (isClosed) {
                stroke = "#ef4444";
                strokeDash = "4 4";
                strokeWidth = 2.2;
              } else if (isFirstHop) {
                stroke = "#d97706";
                strokeWidth = 4.5;
                marker = "url(#arrow-first-hop)";
              } else if (isRoute) {
                stroke = "#059669";
                strokeWidth = 3.5;
                marker = "url(#arrow-route)";
              }

              return (
                <line
                  key={`edge-${idx}`}
                  x1={u.x}
                  y1={u.y}
                  x2={v.x}
                  y2={v.y}
                  stroke={stroke}
                  strokeWidth={strokeWidth}
                  strokeDasharray={strokeDash}
                  markerEnd={marker}
                />
              );
            })}

            {/* Nodes */}
            {graphData.nodes.map((node) => {
              const isObserver = node.id === junctionId;
              const isTarget = node.id === targetDestId;
              const isJunction = node.kind === "junction";

              let fill = isJunction ? "#3b82f6" : "#8b5cf6";
              let radius = 12;

              if (isObserver) {
                fill = "#f59e0b"; // Observer amber
                radius = 16;
              } else if (isTarget) {
                fill = "#10b981"; // Target emerald
                radius = 16;
              }

              return (
                <g key={`node-${node.id}`} className="cursor-pointer">
                  {/* Outer pulse ring for observer */}
                  {isObserver && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={radius + 6}
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth="2"
                      opacity="0.6"
                      className="animate-ping"
                    />
                  )}
                  {/* Outer ring for target */}
                  {isTarget && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={radius + 4}
                      fill="none"
                      stroke="#10b981"
                      strokeWidth="2"
                      opacity="0.7"
                    />
                  )}
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={radius}
                    fill={fill}
                    stroke="#1e293b"
                    strokeWidth="2"
                  />
                  <text
                    x={node.x}
                    y={node.y + radius + 14}
                    textAnchor="middle"
                    className="text-[11px] font-medium fill-slate-800 pointer-events-none"
                  >
                    {node.label_en.split("(")[0].trim()}
                  </text>
                  <text
                    x={node.x}
                    y={node.y + radius + 25}
                    textAnchor="middle"
                    className="text-[9px] font-mono fill-slate-500 pointer-events-none"
                  >
                    [{node.id}]
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Legend */}
          <div className="mt-2 pt-2 border-t border-slate-200/80 flex flex-wrap items-center justify-between text-xs text-slate-600 px-2 gap-y-1">
            <div className="flex items-center space-x-4">
              <span className="flex items-center">
                <span className="w-3 h-3 rounded-full bg-amber-500 mr-1.5 border border-slate-800"></span>
                Observer at <code className="ml-1 font-mono text-[11px]">{junctionId}</code>
              </span>
              <span className="flex items-center">
                <span className="w-3 h-3 rounded-full bg-emerald-500 mr-1.5 border border-slate-800"></span>
                Target: <code className="ml-1 font-mono text-[11px]">{targetDestId}</code>
              </span>
            </div>
            <div className="flex items-center space-x-4">
              <span className="flex items-center">
                <span className="w-4 h-1 bg-amber-600 mr-1.5 rounded"></span>
                First Hop (Gold)
              </span>
              <span className="flex items-center">
                <span className="w-4 h-0.5 bg-emerald-600 mr-1.5 rounded"></span>
                Shortest Path
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
