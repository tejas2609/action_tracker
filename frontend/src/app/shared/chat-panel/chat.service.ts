import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { ChatPage } from "../../core/models";
@Injectable({ providedIn: "root" })
export class ChatService {
  private api = inject(Api);
  list(peerId: string, before?: string): Promise<ChatPage> {
    return this.api.call(
      "GET",
      "/chat/" +
        encodeURIComponent(peerId) +
        (before ? "?before=" + encodeURIComponent(before) : ""),
      undefined,
      true,
    );
  }
  send(
    peerId: string,
    body: string,
    commitmentId?: string,
    quiet = false,
  ): Promise<unknown> {
    return this.api.call(
      "POST",
      "/chat/" + encodeURIComponent(peerId),
      { body, ...(commitmentId ? { commitment_id: commitmentId } : {}) },
      quiet,
    );
  }
}
