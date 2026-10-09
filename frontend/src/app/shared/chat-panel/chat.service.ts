import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { ChatPage, ChatMessage, Page, ChatInboxUser } from "../../core/models";
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
  ): Promise<ChatMessage> {
    return this.api.call(
      "POST",
      "/chat/" + encodeURIComponent(peerId),
      { body, ...(commitmentId ? { commitment_id: commitmentId } : {}) },
      quiet,
    );
  }
    inbox(page = 1): Promise<Page<ChatInboxUser>> {
    return this.api.call(
      "GET",
      `/chat-inbox?page=${page}&page_size=100`,
      undefined,
      true,
    );
  }

  markRead(peerId: string, throughId: string): Promise<unknown> {
    return this.api.call(
      "POST",
      `/chat/${encodeURIComponent(peerId)}/read`,
      { through_id: throughId },
      true,
    );
  }
}
