import { DashboardData } from "./dashboard.service";
import { CommitmentsService } from "../commitments/commitments.service";
import { DashboardService } from "./dashboard.service";
import { SessionService } from "../../core/session.service";
import {
  Component,
  inject,
  signal,
  effect,
  ChangeDetectionStrategy,
} from "@angular/core";
import { RouterLink } from "@angular/router";

import { Api } from "../../core/api.service";
import { Commitment, Page } from "../../core/models";
import { CommitmentList } from "../../shared/commitment-list/commitment-list.component";
import { DependencyGraph } from "../../shared/dependency-graph/dependency-graph.component";
import { Pagination } from "../../shared/pagination/pagination.component";

@Component({
  standalone: true,
  imports: [RouterLink, CommitmentList, DependencyGraph, Pagination],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./dashboard.component.html",
  styleUrl: "./dashboard.component.scss",
})
export class Dashboard {
  commitmentData = inject(CommitmentsService);

  dashboardData = inject(DashboardService);

  session = inject(SessionService);

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

    try {
      const result = await this.dashboardData.load(
        missedPage,
        upcomingPage,
        this.pageSize,
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
      const result = await this.commitmentData.graph("connected");

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
