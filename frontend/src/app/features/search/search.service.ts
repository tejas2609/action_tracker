import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { Commitment } from "../../core/models";

export interface SearchSummary {
  total: number;
  open: number;
  completed: number;
  cancelled: number;
  at_risk: number;
  blocked: number;
  overdue: number;
  missing_deadline: number;
}

export interface SearchGroup extends SearchSummary {
  owner_id: string | null;
  owner: string;
}

export interface SearchResponse {
  interpretation: string;
  results: Commitment[];
  dependencies: Commitment[];
  results_truncated: boolean;
  summary: Partial<SearchSummary>;
  groups: SearchGroup[];
}

@Injectable({ providedIn: "root" })
export class SearchService {
  private api = inject(Api);

  search(query: string): Promise<SearchResponse> {
    return this.api.call("POST", "/search", { query });
  }
}