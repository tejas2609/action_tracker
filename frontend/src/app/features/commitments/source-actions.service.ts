import { inject, Injectable } from "@angular/core";

import { Api } from "../../core/api.service";
import { Page } from "../../core/models";

export interface SourceItem {
  id: string;
  source: string;
  kind: string;
  sender: string;
  received_at: string;
  description: string;
  evidence: string;
  body_text: string;
}

export interface SourceProposal extends SourceItem {
  title: string;
  due_date: string | null;
}

@Injectable({ providedIn: "root" })
export class SourceActionsService {
  private api = inject(Api);

  review(page: number): Promise<Page<SourceProposal>> {
    return this.api.call(
      "GET",
      `/source-review?page=${page}&page_size=10`,
    );
  }

  accept(item: SourceProposal): Promise<{ id: string }> {
    return this.api.call(
      "POST",
      `/source-review/${encodeURIComponent(item.id)}/accept`,
      {
        title: item.title,
        due_date: item.due_date || null,
      },
    );
  }

  reject(id: string): Promise<unknown> {
    return this.api.call(
      "DELETE",
      `/source-review/${encodeURIComponent(id)}`,
    );
  }

  sources(id: string, page: number): Promise<Page<SourceItem>> {
    return this.api.call(
      "GET",
      `/commitments/${encodeURIComponent(id)}/sources` +
        `?page=${page}&page_size=10`,
    );
  }
}