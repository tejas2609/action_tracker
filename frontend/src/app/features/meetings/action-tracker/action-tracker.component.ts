import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  signal,
  untracked,
} from "@angular/core";

import { RouterLink } from "@angular/router";

import { Api } from "../../../core/api.service";
import { AgendaDetail, AgendaSummary } from "./agenda.models";
import { AgendaService } from "./agenda.service";
import { AgendaGraphComponent } from "./agenda-graph.component";

@Component({
  selector: "app-meeting-action-tracker",
  standalone: true,
  imports: [
    RouterLink,
    AgendaGraphComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./action-tracker.component.html",
  styleUrl: "./action-tracker.component.scss",
})
export class MeetingActionTracker {
  private data = inject(AgendaService);
  private api = inject(Api);

  private destroyed = false;
  private listRequest = 0;
  private detailRequest = 0;

  tab = signal<"active" | "completed">("active");
  page = signal(1);
  total = signal(0);

  items = signal<AgendaSummary[]>([]);
  selectedId = signal<string | null>(null);
  selected = signal<AgendaDetail | null>(null);

  mode = signal<"within" | "across">("within");

  loading = signal(false);
  detailLoading = signal(false);

  error = signal("");
  detailError = signal("");

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      this.listRequest++;
      this.detailRequest++;
    });

    effect(() => {
      const tab = this.tab();
      const page = this.page();

      // Reload after an existing operation calls api.changed().
      this.api.revision();

      untracked(() => {
        void this.load(tab, page);
      });
    });
  }

  changeTab(tab: "active" | "completed") {
    this.tab.set(tab);
    this.page.set(1);
    this.clearSelection();
  }

  private clearSelection() {
    this.detailRequest++;
    this.selectedId.set(null);
    this.selected.set(null);
    this.detailLoading.set(false);
    this.detailError.set("");
  }

  refresh() {
    void this.load(this.tab(), this.page());
  }

  private async load(
    tab: "active" | "completed",
    page: number,
  ) {
    const token = ++this.listRequest;

    this.loading.set(true);
    this.error.set("");

    try {
      const result = await this.data.list(tab, page);

      if (this.destroyed || token !== this.listRequest) {
        return;
      }

      // Handle a last page becoming empty after an agenda moves tabs.
      if (!result.items.length && page > 1) {
        this.page.set(
          Math.max(1, Math.ceil(result.total / 10)),
        );
        return;
      }

      this.items.set(result.items);
      this.total.set(result.total);

      const id = this.selectedId();

      if (id && result.items.some(item => item.id === id)) {
        void this.open(id);
      } else {
        this.clearSelection();
      }
    } catch {
      if (token === this.listRequest && !this.destroyed) {
        this.error.set(
          "Unable to load agendas. Please retry.",
        );
      }
    } finally {
      if (token === this.listRequest && !this.destroyed) {
        this.loading.set(false);
      }
    }
  }

  async open(id: string) {
    const token = ++this.detailRequest;

    this.selectedId.set(id);
    this.selected.set(null);
    this.detailLoading.set(true);
    this.detailError.set("");

    try {
      const result = await this.data.detail(id);

      if (token === this.detailRequest && !this.destroyed) {
        this.selected.set(result);
      }
    } catch {
      if (token === this.detailRequest && !this.destroyed) {
        this.detailError.set(
          "Unable to load agenda details. Select the agenda to retry.",
        );
      }
    } finally {
      if (token === this.detailRequest && !this.destroyed) {
        this.detailLoading.set(false);
      }
    }
  }
}