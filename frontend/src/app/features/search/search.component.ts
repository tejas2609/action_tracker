import { SearchService, SearchGroup, SearchSummary } from "./search.service";
import {
  Component,
  inject,
  signal,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Api } from "../../core/api.service";
import { Commitment } from "../../core/models";
import { CommitmentList } from "../../shared/commitment-list/commitment-list.component";
@Component({
  standalone: true,
  imports: [FormsModule, CommitmentList],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./search.component.html",
  styleUrl: "./search.component.scss",
})
export class Search {
  searchData = inject(SearchService);
  api = inject(Api);
  query = "";
  summary = signal<Partial<SearchSummary>>({});
  groups = signal<SearchGroup[]>([]);
  truncated = signal(false);
  examples = [
    "What should I focus on today?",
    "Which of my open commitments are overdue and blocked?",
    "Who has the most open commitments?",
    "What's blocking the launch?",
    "Which commitments have no deadline?",
  ];
  results = signal<Commitment[]>([]);
  interpretation = signal("");
  searched = signal(false);
  async search() {
    try {
      const r = await this.searchData.search(this.query);
      this.results.set(r.results);
      this.interpretation.set(r.interpretation);
      this.summary.set(r.summary);
      this.groups.set(r.groups);
      this.truncated.set(r.results_truncated);
      this.searched.set(true);
    } catch {}
  }
}
