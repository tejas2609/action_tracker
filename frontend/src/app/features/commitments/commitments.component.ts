import {
  CommitmentsService,
  TeamDeadlineFilters,
  MeetingOption,
} from "./commitments.service";
import { A11yModule } from "@angular/cdk/a11y";
import { ActivatedRoute, Router } from "@angular/router";
import { toSignal } from "@angular/core/rxjs-interop";
import { SessionService } from "../../core/session.service";
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
import { EmailReview } from "./email-review/email-review.component";
import { SourceReview } from "./source-review/source-review.component";
@Component({
  standalone: true,
  imports: [
    FormsModule,
    CommitmentList,
    DependencyGraph,
    Pagination,
    EmailReview,
    A11yModule,
    SourceReview
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./commitments.component.html",
  styleUrl: "./commitments.component.scss",
})
export class Commitments {
  commitmentData = inject(CommitmentsService);
  api = inject(Api);
  session = inject(SessionService);
  private router = inject(Router);
  private queryParams = toSignal(inject(ActivatedRoute).queryParamMap);
  view = signal("list");
  loading = signal(false);
  loadError = signal("");
  members = signal<{ id: string; name: string }[]>([]);
  teamForm: TeamDeadlineFilters = {
    q: "",
    owner_id: "",
    due_from: "",
    due_to: "",
    blocked: "all",
    sort: "due_date",
    direction: "asc",
    page_size: 10,
  };
  teamFilters = signal({ ...this.teamForm });
  private request = 0;
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
  showCreate = signal(false);
  createLoading = signal(false);
  createSaving = signal(false);
  createError = signal("");

  meetingChoices = signal<MeetingOption[]>([]);
  prerequisiteChoices = signal<Commitment[]>([]);

  manual = this.emptyManual();

  private emptyManual() {
    return {
      title: "",
      description: "",
      due_date: "",
      progress: 0,
      condition: "",
      condition_met: false,
      blocker: "",
      meeting_id: "",
      prerequisite_ids: [] as string[],
    };
  }
  constructor() {
    effect(() => {
      const requested = this.queryParams()?.get("view");
      this.view.set(
        requested === "team-missed" && this.session.user()?.is_manager
          ? "team-missed"
          : requested === "graph"
            ? "graph"
            : "list",
      );
      this.page.set(1);
    });
    effect(() => {
      this.api.revision();
      const page = this.page(),
        filters = this.filters(),
        mode = this.mode(),
        view = this.view();
      void this.load(page, filters, mode, view, this.teamFilters());
    });
  }
  setView(view: string) {
    void this.router.navigate([], {
      queryParams: { view },
      queryParamsHandling: "merge",
    });
  }
  filterTeam() {
    this.page.set(1);
    this.teamFilters.set({ ...this.teamForm });
  }
  resetTeam() {
    this.teamForm = {
      q: "",
      owner_id: "",
      due_from: "",
      due_to: "",
      blocked: "all",
      sort: "due_date",
      direction: "asc",
      page_size: 10,
    };
    this.filterTeam();
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
    teamFilters: TeamDeadlineFilters,
  ) {
    if (view === "review") return;
    const request = ++this.request;
    this.loading.set(true);
    this.loadError.set("");
    try {
      if (view === "team-missed" && !this.session.user()?.is_manager) return;
      if (view === "list" || view === "team-missed") {
        const r =
          view === "team-missed"
            ? await this.commitmentData.teamMissed(page, teamFilters)
            : await this.commitmentData.list(page, f.q, f.state);
        if (request !== this.request) return;
        if ("members" in r)
          this.members.set(r.members as { id: string; name: string }[]);
        if (r.page !== page) this.page.set(r.page);
        if (page > 1 && !r.items.length) {
          this.page.set(Math.max(1, Math.ceil(r.total / r.page_size)));
          return;
        }
        this.data.set(r);
      } else {
        const result = await this.commitmentData.graph(mode);
        if (request === this.request) this.graph.set(result.items);
      }
    } catch {
      if (request === this.request) {
        this.data.update((d) => ({ ...d, items: [], total: 0 }));
        this.loadError.set(
          "Unable to load commitments. Check your filters and retry.",
        );
      }
    } finally {
      if (request === this.request) this.loading.set(false);
    }
  }
  async openCreate() {
    this.manual = this.emptyManual();
    this.createError.set("");
    this.showCreate.set(true);
    await this.loadCreateOptions();
  }

  async loadCreateOptions() {
    this.createLoading.set(true);
    this.createError.set("");

    try {
      const [meetings, commitments] = await Promise.all([
        this.commitmentData.meetingOptions(),
        this.commitmentData.commitments("organization"),
      ]);

      this.meetingChoices.set(meetings);
      this.prerequisiteChoices.set(
        commitments.filter((item) => item.status !== "cancelled"),
      );
    } catch {
      this.createError.set(
        "Unable to load meetings and prerequisites. Please retry.",
      );
    } finally {
      this.createLoading.set(false);
    }
  }

  async saveManual() {
    if (this.createSaving() || this.createLoading()) return;

    if (!this.manual.title.trim()) {
      this.createError.set("Enter a commitment title.");
      return;
    }

    this.createSaving.set(true);
    this.createError.set("");

    try {
      await this.commitmentData.create({
        ...this.manual,
        title: this.manual.title.trim(),
        due_date: this.manual.due_date || null,
        meeting_id: this.manual.meeting_id || null,
        progress: Number(this.manual.progress),
      });

      this.showCreate.set(false);

      // Clear filters so the new commitment can appear.
      this.text = "";
      this.state = "all";
      this.filters.set({ q: "", state: "all" });
      this.page.set(1);
      this.setView("list");

      // Existing effect reloads the commitment list and graph.
      this.api.changed();
    } catch (error: unknown) {
      const response = error as {
        error?: { detail?: string | unknown[] };
      };

      this.createError.set(
        typeof response.error?.detail === "string"
          ? response.error.detail
          : "Could not create the commitment. Check the details and retry.",
      );
    } finally {
      this.createSaving.set(false);
    }
  }
}
