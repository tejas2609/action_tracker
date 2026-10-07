import { inject, Injectable } from "@angular/core";
import { Api } from "../../core/api.service";
import { Commitment, Page } from "../../core/models";
@Injectable({ providedIn: "root" })
export class CommitmentsService {
  private api = inject(Api);
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
