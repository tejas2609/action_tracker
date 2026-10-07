import { inject, Injectable } from "@angular/core";

import { Api } from "../../core/api.service";
import { Page } from "../../core/models";

export interface EmailProposal {
  id: string;
  title: string;
  due_date: string | null;
  description: string;
  subject: string;
  sender: string;
  received_at: string;
}

export interface EmailSource {
  subject: string;
  sender: string;
  received_at: string;
  body_text: string;
  truncated: boolean;
}

export interface CommitmentEmail extends EmailSource {
  id: string;
  description: string;
}

export interface ScanResult {
  busy: boolean;
  processed: number;
  proposed: number;
  attached: number;
}

@Injectable({ providedIn: "root" })
export class EmailActionsService {
  private api = inject(Api);

  scan(): Promise<ScanResult> {
    return this.api.call("POST", "/integrations/gmail/scan");
  }

  review(page: number): Promise<Page<EmailProposal>> {
    return this.api.call(
      "GET",
      `/email-review?page=${page}&page_size=10`,
    );
  }

  source(id: string): Promise<EmailSource> {
    return this.api.call(
      "GET",
      `/email-review/${encodeURIComponent(id)}/source`,
    );
  }

  accept(
    id: string,
    title: string,
    dueDate: string | null,
  ): Promise<{ id: string }> {
    return this.api.call(
      "POST",
      `/email-review/${encodeURIComponent(id)}/accept`,
      {
        title,
        due_date: dueDate || null,
      },
    );
  }

  reject(id: string): Promise<unknown> {
    return this.api.call(
      "DELETE",
      `/email-review/${encodeURIComponent(id)}`,
    );
  }

  emails(
    commitmentId: string,
    page: number,
  ): Promise<Page<CommitmentEmail>> {
    return this.api.call(
      "GET",
      `/commitments/${encodeURIComponent(commitmentId)}/emails` +
        `?page=${page}&page_size=5`,
    );
  }

  remove(
    commitmentId: string,
    attachmentId: string,
  ): Promise<unknown> {
    return this.api.call(
      "DELETE",
      `/commitments/${encodeURIComponent(commitmentId)}/emails/` +
        encodeURIComponent(attachmentId),
    );
  }
}