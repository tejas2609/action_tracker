export interface AgendaSummary {
  id: string;
  title: string;
  held_on: string;
  review_state: string;
  agenda_state:
    | "active"
    | "completed"
    | "awaiting_review"
    | "no_actions";
  total: number;
  completed: number;
  progress: number;
}

export interface AgendaTask {
  id: string;
  title: string;
  owner: string;
  owner_id: string | null;
  due_date: string | null;
  status: string;
  progress: number;
  ready: boolean;
  reasons: string[];
  external: boolean;
  meeting_id: string | null;
  meeting_title: string;
  prerequisite_ids: string[];
}

export interface AgendaGraph {
  nodes: AgendaTask[];
  edges: {
    source: string;
    target: string;
  }[];
}

export interface AgendaDetail extends AgendaSummary {
  next_steps: string[];
  next_actions: AgendaTask[];
  within: AgendaGraph;
  across: AgendaGraph;
  external_meetings: {
    meeting_id: string;
    title: string;
    coverage: "full" | "partial";
    affected_commitments: number;
    total_commitments: number;
    pending_prerequisites: number;
  }[];
}

export interface AgendaPage {
  items: AgendaSummary[];
  total: number;
  page: number;
  page_size: number;
}