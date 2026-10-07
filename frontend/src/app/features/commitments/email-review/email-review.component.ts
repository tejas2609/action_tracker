import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  inject,
  signal,
} from "@angular/core";

import { DatePipe } from "@angular/common";
import { FormsModule } from "@angular/forms";

import { Api } from "../../../core/api.service";
import { Page } from "../../../core/models";

import {
  EmailActionsService,
  EmailProposal,
  EmailSource,
} from "../email-actions.service";

import { Pagination } from "../../../shared/pagination/pagination.component";

@Component({
  selector: "email-review",
  standalone: true,
  imports: [FormsModule, DatePipe, Pagination],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./email-review.component.html",
  styleUrl: "./email-review.component.scss",
})
export class EmailReview implements OnInit, OnDestroy {
  private service = inject(EmailActionsService);
  private api = inject(Api);

  readonly data = signal<Page<EmailProposal>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });

  readonly page = signal(1);
  readonly working = signal(false);
  readonly loading = signal(false);
  readonly message = signal("");

  readonly source = signal<EmailSource | null>(null);

  private timer?: ReturnType<typeof setInterval>;
  private destroyed = false;

  async ngOnInit(): Promise<void> {
    await this.load();

    // Refresh the review list. Gmail scanning is handled by the worker.
    this.timer = setInterval(() => {
      if (!this.working() && !document.hidden) {
        void this.load();
      }
    }, 30000);
  }

  ngOnDestroy(): void {
    this.destroyed = true;

    if (this.timer) clearInterval(this.timer);
  }

  async load(page = this.page()): Promise<void> {
    if (this.loading()) return;

    this.loading.set(true);

    try {
      const result = await this.service.review(page);

      if (this.destroyed) return;

      if (page > 1 && !result.items.length) {
        this.loading.set(false);

        await this.load(
          Math.max(1, Math.ceil(result.total / result.page_size)),
        );

        return;
      }

      this.page.set(page);
      this.data.set(result);
    } catch {
      // Shared API service exposes errors.
    } finally {
      this.loading.set(false);
    }
  }

  async scan(): Promise<void> {
    if (this.working()) return;

    this.working.set(true);
    this.message.set("");

    try {
      const result = await this.service.scan();

      this.message.set(
        result.busy
          ? "Gmail is already being checked."
          : `Processed ${result.processed} emails. ` +
              `${result.proposed} proposals and ` +
              `${result.attached} attachments added.`,
      );

      this.api.changed();
      await this.load();
    } catch {
      // Shared API service exposes errors.
    } finally {
      this.working.set(false);
    }
  }

  async preview(item: EmailProposal): Promise<void> {
    if (this.working()) return;

    this.working.set(true);

    try {
      this.source.set(await this.service.source(item.id));
    } catch {
      // Shared API service exposes errors.
    } finally {
      this.working.set(false);
    }
  }

  async accept(item: EmailProposal): Promise<void> {
    if (this.working()) return;

    this.working.set(true);

    try {
      await this.service.accept(
        item.id,
        item.title,
        item.due_date,
      );

      this.message.set("Commitment accepted.");
      this.api.changed();

      await this.load();
    } catch {
      // Shared API service exposes errors.
    } finally {
      this.working.set(false);
    }
  }

  async reject(item: EmailProposal): Promise<void> {
    if (
      this.working() ||
      !window.confirm("Reject this proposed commitment?")
    ) {
      return;
    }

    this.working.set(true);

    try {
      await this.service.reject(item.id);

      this.message.set("Proposal rejected.");
      this.api.changed();

      await this.load();
    } catch {
      // Shared API service exposes errors.
    } finally {
      this.working.set(false);
    }
  }
}