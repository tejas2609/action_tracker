import { CommitmentsService } from "./commitments.service";
import {
  Component,
  inject,
  signal,
  effect,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Api } from "../../core/api.service";
import { Commitment, Page } from "../../core/models";
import { CommitmentList } from "../../shared/commitment-list/commitment-list.component";
import { DependencyGraph } from "../../shared/dependency-graph/dependency-graph.component";
import { Pagination } from "../../shared/pagination/pagination.component";
@Component({
  standalone: true,
  imports: [FormsModule, CommitmentList, DependencyGraph, Pagination],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./commitments.component.html",
  styleUrl: "./commitments.component.scss",
})
export class Commitments {
  commitmentData = inject(CommitmentsService);
  api = inject(Api);
  view = signal("list");
  mode = signal("immediate");
  page = signal(1);
  text = "";
  state = "all";
  filters = signal({ q: "", state: "all" });
  data = signal<Page<Commitment>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });
  graph = signal<Commitment[]>([]);
  constructor() {
    effect(() => {
      this.api.revision();
      const page = this.page(),
        filters = this.filters(),
        mode = this.mode(),
        view = this.view();
      void this.load(page, filters, mode, view);
    });
  }
  filter() {
    this.page.set(1);
    this.filters.set({ q: this.text, state: this.state });
  }
  async load(
    page: number,
    f: { q: string; state: string },
    mode: string,
    view: string,
  ) {
    try {
      if (view === "list") {
        const r = await this.commitmentData.list(page, f.q, f.state);
        if (page > 1 && !r.items.length) {
          this.page.set(Math.max(1, Math.ceil(r.total / 10)));
          return;
        }
        this.data.set(r);
      } else this.graph.set((await this.commitmentData.graph(mode)).items);
    } catch {
      this.api.error.set("Unable to load your commitments. Check the backend.");
    }
  }
}
