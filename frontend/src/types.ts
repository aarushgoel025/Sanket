export interface TaskReceipt {
  solver_answer: string;
  independent_answer: string;
  agree: boolean;
  fidelity_ok: boolean;
  visibility_ok: boolean;
  evidence_visible_ratio: number;
  blind_correct_rate: number;
  blind_rejected: boolean;
  pair_verified?: boolean;
  human_audit?: string;
  notes?: string;
}

export interface SignEntry {
  destination_id: string;
  arrow_angle: number;
  is_closed?: boolean;
  is_override?: boolean;
  bounding_box?: [number, number, number, number]; // [ymin, xmin, ymax, xmax]
}

export interface TaskScene {
  venue_id: string;
  junction_id: string;
  heading: number;
  entries?: SignEntry[];
  closed_edges?: [string, string][];
}

export interface Task {
  task_id: string;
  schema_version?: string;
  generator_version?: string;
  seed: number;
  qtype: string;
  question: string;
  options: string[];
  gold: string;
  image_path: string;
  image_url: string;
  scene_path: string;
  target_dest_id: string;
  turn_cw?: number | null;
  skill_tags?: string[];
  difficulty?: {
    n_entries?: number;
    perspective_deg?: number;
    blur?: number;
    noise?: number;
    lighting?: number;
    clutter?: number;
    occlusion?: number;
    jpeg_quality?: number;
    template?: string;
  };
  pair_id?: string | null;
  pair_role?: string | null;
  receipt?: TaskReceipt;
  scene?: TaskScene;
}

export interface VenueInfo {
  id: string;
  name: string;
  node_count: number;
  edge_count: number;
  junctions: string[];
  destinations: string[];
}

export interface GraphNode {
  id: string;
  label_en: string;
  label_hi?: string;
  kind: "junction" | "destination" | string;
  x: number;
  y: number;
}

export interface GraphEdge {
  from_node: string;
  to_node: string;
  bearing: number;
  length: number;
  level: number;
}

export interface VenueGraphData {
  venue_id: string;
  name: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface MinimalPair {
  pair_id: string;
  qtype: string;
  task_a: Task;
  task_b: Task;
  gold_a: string;
  gold_b: string;
  golds_differ: boolean;
}

export interface AskResult {
  task_id: string;
  model_name: string;
  mode: string;
  gold_answer: string;
  model_answer: string;
  is_correct: boolean;
  latency_s: number;
  raw_response: string;
  source: string;
}

export interface FindingFigure {
  id: string;
  title: string;
  takeaway: string;
  url: string;
  file: string;
}

export interface ModelMetric {
  model: string;
  mode: string;
  tasks: number;
  correct: number;
  acc: number;
  ci: string;
}

export interface FindingsData {
  figures: FindingFigure[];
  model_metrics: ModelMetric[];
  perception_gap: Record<string, { image_acc: number; text_acc: number; gap_pp: number }>;
}

export interface FailureCase {
  task_id: string;
  qtype: string;
  image_url: string;
  question: string;
  gold: string;
  model_pred: string;
  model_name: string;
  mode: string;
  failure_reason: string;
  explanation: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  real_world_consequence: string;
}
