import { SearchService } from "./search.service";
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
  examples = [
    "What's blocking the launch?",
    "What did Sarah promise?",
    "Which commitments are at risk?",
  ];
  results = signal<Commitment[]>([]);
  interpretation = signal("");
  searched = signal(false);
  async search() {
    try {
      const r = await this.searchData.search(this.query);
      this.results.set(r.results);
      this.interpretation.set(r.interpretation);
      this.searched.set(true);
    } catch {}
  }
}
