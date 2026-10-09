import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  signal,
} from "@angular/core";
import { DatePipe } from "@angular/common";
import { FormsModule } from "@angular/forms";

import { Api } from "../../../core/api.service";
import { Page } from "../../../core/models";
import {
  SourceActionsService,
  SourceProposal,
} from "../source-actions.service";

@Component({
  selector: "source-review",
  standalone: true,
  imports: [DatePipe, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./source-review.component.html",
  styleUrls: ["./source-review.component.scss"],
})
export class SourceReview {
  private service = inject(SourceActionsService);
  private api = inject(Api);
  private destroyRef = inject(DestroyRef);
  private destroyed = false;

  readonly page = signal(1);
  readonly loading = signal(false);
  readonly working = signal(false);

  readonly data = signal<Page<SourceProposal>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });

  async load(page = this.page()): Promise<void> {
    if (this.loading() || this.destroyed) return;

    this.loading.set(true);

    try {
      const result = await this.service.review(page);

      if (!this.destroyed) {
        this.page.set(page);
        this.data.set(result);
      }
    } catch {
      // Api exposes the error.
    } finally {
      if (!this.destroyed) this.loading.set(false);
    }
  }

  constructor() {
    void this.load();

    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
    });
  }

  async decide(
    item: SourceProposal,
    accept: boolean,
  ): Promise<void> {
    if (this.working() || this.loading()) return;

    this.working.set(true);

    try {
      if (accept) {
        await this.service.accept(item);
      } else {
        await this.service.reject(item.id);
      }

      this.api.changed();

      if (!this.destroyed) await this.load(1);
    } catch {
      // Api exposes the error.
    } finally {
      if (!this.destroyed) this.working.set(false);
    }
  }
}