import { inject, Injectable } from "@angular/core";
import { Api } from "../../core/api.service";
import { Commitment, Page } from "../../core/models";
export interface TeamDeadlineFilters {
  q: string;
  owner_id: string;
  due_from: string;
  due_to: string;
  blocked: string;
  sort: string;
  direction: string;
  page_size: number;
}
export interface TeamDeadlinePage extends Page<Commitment> {
  members: { id: string; name: string }[];
}
@Injectable({ providedIn: "root" })
export class CommitmentsService {
  private api = inject(Api);
  teamMissed(page: number, filters: TeamDeadlineFilters): Promise<TeamDeadlinePage> {
    const params = new URLSearchParams({ page: String(page) });
    for (const [key, value] of Object.entries(filters)) {
      if (value !== "") params.set(key, String(value));
    }
    return this.api.call("GET", "/team-missed-deadlines?" + params, undefined, true);
  }
  list(page: number, q: string, state: string): Promise<Page<Commitment>> {
    const params = new URLSearchParams({ page: String(page), q, state });
    return this.api.call(
      "GET",
      "/commitments?" + params.toString(),
      undefined,
      true,
    );
  }
  graph(mode: string): Promise<{ items: Commitment[] }> {
    return this.api.call(
      "GET",
      "/graph?mode=" + encodeURIComponent(mode),
      undefined,
      true,
    );
  }
  get(id: string): Promise<Commitment> {
    return this.api.call(
      "GET",
      "/commitments/" + encodeURIComponent(id),
      undefined,
      true,
    );
  }
  update(id: string, body: unknown): Promise<unknown> {
    return this.api.call(
      "PATCH",
      "/commitments/" + encodeURIComponent(id),
      body,
    );
  }
  analyze(id: string): Promise<unknown> {
    return this.api.call(
      "POST",
      `/commitments/${encodeURIComponent(id)}/analysis`,
      undefined,
      true,
    );
  }
  followup(id: string, recipientId: string): Promise<{ message: string }> {
    return this.api.call(
      "POST",
      `/commitments/${encodeURIComponent(id)}/followup`,
      { recipient_id: recipientId },
    );
  }
  dependencyMutation(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<unknown> {
    return this.api.call(method, path, body);
  }
  async commitments(scope = "organization"): Promise<Commitment[]> {
    let page = 1;
    const rows: Commitment[] = [];
    while (true) {
      const result = await this.api.call<Page<Commitment>>(
        "GET",
        `/commitments?scope=${encodeURIComponent(scope)}&page_size=100&page=${page}`,
        undefined,
        true,
      );
      rows.push(...result.items);
      if (rows.length >= result.total || !result.items.length) return rows;
      page++;
    }
  }
}
