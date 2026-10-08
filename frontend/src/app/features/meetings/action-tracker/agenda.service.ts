import { Injectable, inject } from "@angular/core";

import { Api } from "../../../core/api.service";
import { AgendaDetail, AgendaPage } from "./agenda.models";

@Injectable({ providedIn: "root" })
export class AgendaService {
  private api = inject(Api);

  list(
    tab: "active" | "completed",
    page: number,
  ): Promise<AgendaPage> {
    return this.api.call(
      "GET",
      `/meeting-agendas?tab=${tab}&page=${page}&page_size=10`,
      undefined,
      true,
    );
  }

  detail(id: string): Promise<AgendaDetail> {
    return this.api.call(
      "GET",
      `/meeting-agendas/${encodeURIComponent(id)}`,
      undefined,
      true,
    );
  }
}