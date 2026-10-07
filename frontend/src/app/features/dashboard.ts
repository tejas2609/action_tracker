import {
  Component,
  inject,
  signal,
  effect,
  ChangeDetectionStrategy,
} from "@angular/core";
import { RouterLink } from "@angular/router";

import { Api } from "../core/api";
import { Commitment, Page } from "../core/models";
import { CommitmentList } from "../shared/commitment-list";
import { DependencyGraph } from "../shared/dependency-graph";
import { Pagination } from "../shared/pagination";

interface DashboardData {
  metrics: Record<string, number>;
  missed: Page<Commitment>;
  upcoming: Page<Commitment>;
}

@Component({
  standalone: true,
  imports: [RouterLink, CommitmentList, DependencyGraph, Pagination],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="eyebrow">YOUR COMMITMENT CONTROL CENTER</div>

    <div class="page-title">
      <div>
        <h1>Keep your promises moving.</h1>
        <p>{{ api.user()?.name }}, here's what needs your attention next.</p>
      </div>

      <a class="button primary" routerLink="/meetings"> + Add a meeting </a>
    </div>

    @if (data(); as d) {
      <div class="metrics v2-metrics">
        @for (m of metrics(d); track m.label) {
          <div class="metric">
            <span>{{ m.label }}</span>
            <strong>{{ m.value }}</strong>
          </div>
        }
      </div>

      <div class="dashboard-deadline-cards" [attr.aria-busy]="loading()">
        <section>
          <div class="section-heading">
            <div>
              <h2>Missed deadlines</h2>
              <p class="muted">Active commitments whose deadline has passed.</p>
            </div>

            <span class="badge high"> {{ d.missed.total }} missed </span>
          </div>

          @if (d.missed.total > 0) {
            <commitment-list [items]="d.missed.items" />
          } @else {
            <p class="empty">No missed deadlines.</p>
          }

          <div
            class="dashboard-card-pagination"
            [class.is-loading]="loading()"
            [attr.inert]="loading() ? '' : null"
          >
            <page-controls
              [total]="d.missed.total"
              [page]="d.missed.page"
              [size]="d.missed.page_size"
              (change)="changeMissedPage($event)"
            />
          </div>
        </section>

        <section>
          <div class="section-heading">
            <div>
              <h2>Upcoming tasks</h2>
              <p class="muted">Active commitments due today or later.</p>
            </div>

            <span class="badge medium"> {{ d.upcoming.total }} upcoming </span>
          </div>

          @if (d.upcoming.total > 0) {
            <commitment-list [items]="d.upcoming.items" />
          } @else {
            <p class="empty">No upcoming tasks.</p>
          }

          <div
            class="dashboard-card-pagination"
            [class.is-loading]="loading()"
            [attr.inert]="loading() ? '' : null"
          >
            <page-controls
              [total]="d.upcoming.total"
              [page]="d.upcoming.page"
              [size]="d.upcoming.page_size"
              (change)="changeUpcomingPage($event)"
            />
          </div>
        </section>
      </div>

      <section>
        <h2>Your dependency landscape</h2>
        <p class="muted">
          All your commitments and their connected upstream/downstream context.
        </p>
        <dependency-graph [items]="graph()" />
      </section>
    }
  `,
})
export class Dashboard {
  api = inject(Api);

  data = signal<DashboardData | null>(null);
  graph = signal<Commitment[]>([]);
  loading = signal(false);

  missedPage = signal(1);
  upcomingPage = signal(1);

  readonly pageSize = 5;

  private dashboardRequest = 0;
  private graphRequest = 0;

  constructor() {
    // Refresh cards after pagination or commitment changes.
    effect(() => {
      this.api.revision();

      const missedPage = this.missedPage();
      const upcomingPage = this.upcomingPage();

      void this.loadDashboard(missedPage, upcomingPage);
    });

    // Pagination does not need to reload the dependency graph.
    effect(() => {
      this.api.revision();
      void this.loadGraph();
    });
  }

  changeMissedPage(page: number): void {
    if (!this.loading()) {
      this.missedPage.set(page);
    }
  }

  changeUpcomingPage(page: number): void {
    if (!this.loading()) {
      this.upcomingPage.set(page);
    }
  }

  async loadDashboard(missedPage: number, upcomingPage: number): Promise<void> {
    const request = ++this.dashboardRequest;
    this.loading.set(true);

    const params = new URLSearchParams({
      missed_page: String(missedPage),
      upcoming_page: String(upcomingPage),
      page_size: String(this.pageSize),
    });

    try {
      const result = await this.api.call<DashboardData>(
        "GET",
        "/dashboard?" + params.toString(),
        undefined,
        true,
      );

      // Ignore an older response if a newer request has started.
      if (request !== this.dashboardRequest) return;

      this.data.set(result);

      // Backend clamps pages when tasks move or disappear.
      if (this.missedPage() !== result.missed.page) {
        this.missedPage.set(result.missed.page);
      }

      if (this.upcomingPage() !== result.upcoming.page) {
        this.upcomingPage.set(result.upcoming.page);
      }
    } catch {
      if (request === this.dashboardRequest) {
        this.api.error.set(
          "Unable to load dashboard. Check the backend and retry.",
        );
      }
    } finally {
      if (request === this.dashboardRequest) {
        this.loading.set(false);
      }
    }
  }

  async loadGraph(): Promise<void> {
    const request = ++this.graphRequest;

    try {
      const result = await this.api.call<{
        items: Commitment[];
      }>("GET", "/graph?mode=connected", undefined, true);

      if (request === this.graphRequest) {
        this.graph.set(result.items);
      }
    } catch {
      if (request === this.graphRequest) {
        this.api.error.set("Unable to load the dependency landscape.");
      }
    }
  }

  metrics(d: DashboardData) {
    return [
      { label: "Total promises", value: d.metrics["total"] },
      { label: "Active", value: d.metrics["active"] },
      { label: "On track", value: d.metrics["on_track"] },
      { label: "At risk", value: d.metrics["at_risk"] },
      {
        label: "Waiting / blocked",
        value: d.metrics["blocked"],
      },
      {
        label: "Deadline passed",
        value: d.metrics["overdue"],
      },
      { label: "Completed", value: d.metrics["completed"] },
    ];
  }
}
