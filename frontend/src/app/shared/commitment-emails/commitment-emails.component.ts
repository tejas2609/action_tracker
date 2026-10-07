import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
} from "@angular/core";

import { DatePipe } from "@angular/common";

import { Page } from "../../core/models";

import {
  CommitmentEmail,
  EmailActionsService,
} from "../../features/commitments/email-actions.service";

import { Pagination } from "../pagination/pagination.component";

@Component({
  selector: "commitment-emails",
  standalone: true,
  imports: [DatePipe, Pagination],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./commitment-emails.component.html",
  styleUrl: "./commitment-emails.component.scss",
})
export class CommitmentEmails {
  commitmentId = input.required<string>();

  private service = inject(EmailActionsService);

  readonly data = signal<Page<CommitmentEmail>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 5,
  });

  readonly loading = signal(false);
  readonly error = signal("");

  private request = 0;

  constructor() {
    effect(() => {
      const id = this.commitmentId();

      void this.load(1, id);
    });
  }

  async load(
    page = 1,
    id = this.commitmentId(),
  ): Promise<void> {
    const request = ++this.request;

    this.loading.set(true);
    this.error.set("");

    try {
      const result = await this.service.emails(id, page);

      if (request !== this.request) return;

      if (page > 1 && !result.items.length) {
        await this.load(
          Math.max(1, Math.ceil(result.total / 5)),
          id,
        );

        return;
      }

      this.data.set(result);
    } catch {
      if (request === this.request) {
        this.error.set("Unable to load email attachments.");
      }
    } finally {
      if (request === this.request) {
        this.loading.set(false);
      }
    }
  }

  async remove(item: CommitmentEmail): Promise<void> {
    if (!window.confirm("Remove this email attachment?")) return;

    const id = this.commitmentId();

    try {
      await this.service.remove(id, item.id);

      if (id === this.commitmentId()) {
        await this.load(this.data().page);
      }
    } catch {
      this.error.set("Unable to remove the email attachment.");
    }
  }
}