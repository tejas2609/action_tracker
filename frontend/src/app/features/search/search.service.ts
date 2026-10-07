import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { Commitment } from "../../core/models";
@Injectable({ providedIn: "root" })
export class SearchService {
  private api = inject(Api);
  search(
    query: string,
  ): Promise<{ interpretation: string; results: Commitment[] }> {
    return this.api.call("POST", "/search", { query });
  }
}
