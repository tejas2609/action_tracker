import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  signal,
  untracked,
} from "@angular/core";
import { DatePipe } from "@angular/common";

import { Api } from "../../core/api.service";
import { Page } from "../../core/models";
import {
  SourceActionsService,
  SourceItem,
} from "../../features/commitments/source-actions.service";

@Component({
  selector: "commitment-sources",
  standalone: true,
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./commitment-sources.component.html",
  styleUrls: ["./commitment-sources.component.scss"],
})
export class CommitmentSources {
  readonly commitmentId = input.required<string>();

  private service = inject(SourceActionsService);
  private api = inject(Api);
  private destroyRef = inject(DestroyRef);

  private generation = 0;
  private destroyed = false;

  readonly page = signal(1);
  readonly loading = signal(false);
  readonly error = signal("");

  readonly data = signal<Page<SourceItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });

  constructor() {
    effect(() => {
      this.commitmentId();
      this.api.revision();

      this.generation++;
      this.loading.set(false);
      this.page.set(1);

      this.data.set({
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
      });

      untracked(() => {
        void this.load(1);
      });
    });

    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
      this.generation++;
    });
  }

  async load(page = this.page()): Promise<void> {
    if (this.loading() || this.destroyed) return;

    const generation = this.generation;

    this.loading.set(true);
    this.error.set("");

    try {
      const result = await this.service.sources(
        this.commitmentId(),
        page,
      );

      if (generation === this.generation) {
        this.page.set(page);
        this.data.set(result);
      }
    } catch {
      if (generation === this.generation) {
        this.error.set("Could not load source messages.");
      }
    } finally {
      if (generation === this.generation) {
        this.loading.set(false);
      }
    }
  }
}