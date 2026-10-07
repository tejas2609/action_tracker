export interface User {
  id: string;
  organization_id: string;
  name: string;
  email: string;
  team: string;
  role: string;
  active: boolean;
  is_manager: boolean;
  manager_id: string | null;
}
export interface Risk {
  level: string;
  reasons: string[];
  state: string;
  next_action: string;
  overdue?: boolean;
}
export interface Commitment {
  id: string;
  title: string;
  owner: string;
  owner_id: string | null;
  due_date: string | null;
  status: string;
  progress: number;
  condition: string;
  condition_met: boolean;
  blocker: string;
  source_statement: string;
  meeting_id: string | null;
  risk: Risk;
  dependencies: string[];
  impact: string[];
  is_mine?: boolean;
  can_edit?: boolean;
  related?: Commitment[];
  analysis?: {
    explanation: string;
    next_action: string;
    stale: boolean;
    revision: string;
  };
  timeline?: {
    id: string;
    kind: string;
    message: string;
    created_at: string;
  }[];
  meeting?: Meeting | null;
}
export interface Finding {
  kind: string;
  title: string;
  owner: string;
  owner_id?: string | null;
  source_line?: number;
  statement: string;
  due_date: string | null;
  condition: string;
  confidence: number;
  explanation: string;
  existing_id: string | null;
  action?: string;
  depends_on_indices: number[];
  prerequisite_ids: string[];
}
export interface Meeting {
  id: string;
  title: string;
  held_on: string;
  transcript: string;
  state: string;
  findings: Finding[];
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface ChatMessage {
  id: string;
  sender_id: string;
  body: string;
  commitment_id: string | null;
  created_at: string;
  attachments: unknown[];
}
export interface ChatPage {
  conversation_id: string;
  peer: User;
  items: ChatMessage[];
  has_more: boolean;
  before: string | null;
}
