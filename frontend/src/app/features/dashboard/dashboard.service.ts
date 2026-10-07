import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { Commitment, Page } from "../../core/models";
export interface DashboardData {
  metrics: Record<string, number>;
  missed: Page<Commitment>;
  upcoming: Page<Commitment>;
}
@Injectable({ providedIn: "root" })
export class DashboardService {
  private api = inject(Api);
  load(
    missedPage: number,
    upcomingPage: number,
    pageSize: number,
  ): Promise<DashboardData> {
    const params = new URLSearchParams({
      missed_page: String(missedPage),
      upcoming_page: String(upcomingPage),
      page_size: String(pageSize),
    });
    return this.api.call(
      "GET",
      "/dashboard?" + params.toString(),
      undefined,
      true,
    );
  }
}
