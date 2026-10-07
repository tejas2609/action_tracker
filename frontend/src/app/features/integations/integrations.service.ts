import { inject, Injectable } from "@angular/core";

import { Api } from "../../core/api.service";

export interface GmailStatus {
  configured: boolean;
  connected: boolean;

  account: {
    email: string;
    name: string;
    connected_at: string;
  } | null;
}

@Injectable({
  providedIn: "root",
})
export class IntegrationsService {
  private api = inject(Api);

  status(): Promise<GmailStatus> {
    return this.api.call<GmailStatus>(
      "GET",
      "/integrations/gmail",
    );
  }

  connect(): Promise<{ authorization_url: string }> {
    return this.api.call<{ authorization_url: string }>(
      "POST",
      "/integrations/gmail/connect",
    );
  }

  disconnect(): Promise<GmailStatus> {
    return this.api.call<GmailStatus>(
      "DELETE",
      "/integrations/gmail",
    );
  }
}