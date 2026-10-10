import {
  Component,
  ChangeDetectionStrategy,
  ElementRef,
  OnDestroy,
  ViewChild,
  inject,
  signal,
  effect,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";

import { ChatService } from "../../shared/chat-panel/chat.service";
import { SessionService } from "../../core/session.service";
import { ChatInboxUser, ChatMessage } from "../../core/models";
import { ActivatedRoute } from "@angular/router";
import { toSignal } from "@angular/core/rxjs-interop";

@Component({
  selector: "app-chat",
  standalone: true,
  imports: [FormsModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./chat.component.html",
  styleUrl: "./chat.component.scss",
})
export class Chat implements OnDestroy {
  private chat = inject(ChatService);
  session = inject(SessionService);

  users = signal<ChatInboxUser[]>([]);
  selected = signal<ChatInboxUser | null>(null);
  messages = signal<ChatMessage[]>([]);
  error = signal("");
  sending = signal(false);
  hasMore = signal(false);

  draft = "";
  page = signal(1);
  total = signal(0);

  private before: string | null = null;
  private busy = false;
  private destroyed = false;
  private timer: ReturnType<typeof setInterval>;

  @ViewChild("scrollArea")
  scroll?: ElementRef<HTMLElement>;

  private queryParams = toSignal(inject(ActivatedRoute).queryParamMap);

  private targetRequest = 0;
  readonly openingPeer = signal(false);

  private async openPeer(peerId: string | null) {
    const request = ++this.targetRequest;

    if (!peerId || this.selected()?.id === peerId) {
      this.openingPeer.set(false);
      return;
    }

    this.openingPeer.set(true);

    try {
      // Direct lookup works even when the peer is on another inbox page.
      const result = await this.chat.list(peerId);

      if (this.destroyed || request !== this.targetRequest) return;

      this.selected.set({
        ...result.peer,
        conversation_id: result.conversation_id,
        last_message_at: result.items.at(-1)?.created_at ?? null,
        unread_count: 0,
      });

      this.messages.set(result.items);
      this.before = result.before;
      this.hasMore.set(result.has_more);
      this.draft = "";
      this.error.set("");
      this.bottom();
    } catch {
      if (!this.destroyed && request === this.targetRequest) {
        this.error.set("Unable to open this conversation.");
      }
    } finally {
      if (!this.destroyed && request === this.targetRequest) {
        this.openingPeer.set(false);
        void this.refresh();
      }
    }
  }

  constructor() {
    effect(() => {
      const peerId = this.queryParams()?.get("peer") ?? null;
      void this.openPeer(peerId);
    });
    void this.refresh();

    this.timer = setInterval(() => {
      if (!document.hidden) void this.refresh();
    }, 3000);
  }

  choose(user: ChatInboxUser) {
    ++this.targetRequest;
    this.openingPeer.set(false);
    if (this.selected()?.id === user.id) return;

    this.selected.set(user);
    this.messages.set([]);
    this.hasMore.set(false);
    this.before = null;
    this.draft = "";

    void this.refresh();
  }

  async changePage(direction: number) {
    const next = this.page() + direction;
    if (next < 1 || (next - 1) * 100 >= this.total()) return;

    this.page.set(next);
    await this.refresh();
  }

  private merge(items: ChatMessage[]) {
    const merged = new Map(
      [...this.messages(), ...items].map((m) => [m.id, m]),
    );

    this.messages.set(
      [...merged.values()].sort(
        (a, b) =>
          a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id),
      ),
    );
  }

  async refresh() {
    if (this.busy || this.destroyed || this.openingPeer()) return;
    this.busy = true;

    try {
      const inbox = await this.chat.inbox(this.page());
      if (this.destroyed) return;

      this.users.set(inbox.items);
      this.total.set(inbox.total);

      const peer = this.selected();
      if (!peer) {
        this.error.set("");
        return;
      }

      const currentId = peer.id;
      const result = await this.chat.list(currentId);

      if (this.destroyed || this.selected()?.id !== currentId) return;

      const firstLoad = this.messages().length === 0;
      this.merge(result.items);

      if (firstLoad) {
        this.before = result.before;
        this.hasMore.set(result.has_more);
        this.bottom();
      }

      // Allow the selected conversation to render before marking it read.
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => resolve()),
      );

      const last = result.items.at(-1);

      if (
        last &&
        !document.hidden &&
        !this.destroyed &&
        this.selected()?.id === currentId
      ) {
        await this.chat.markRead(currentId, last.id);

        // Refresh from the server instead of forcing the count to zero:
        // another message may have arrived after the read cursor.
        const updated = await this.chat.inbox(this.page());
        if (!this.destroyed) {
          this.users.set(updated.items);
          this.total.set(updated.total);
        }
      }

      this.error.set("");
    } catch {
      if (!this.destroyed) {
        this.error.set("Could not refresh chat. Retrying automatically.");
      }
    } finally {
      this.busy = false;
    }
  }

  async older() {
    const peer = this.selected();
    if (!peer || !this.before) return;

    try {
      const result = await this.chat.list(peer.id, this.before);

      if (this.destroyed || this.selected()?.id !== peer.id) return;

      this.merge(result.items);
      this.before = result.before;
      this.hasMore.set(result.has_more);
    } catch {
      this.error.set("Could not load older messages.");
    }
  }

  async send() {
    const peer = this.selected();
    const body = this.draft.trim();

    if (!peer || !body || this.sending()) return;

    this.sending.set(true);

    try {
      await this.chat.send(peer.id, body, undefined, true);

      if (this.selected()?.id === peer.id) {
        this.draft = "";
        await this.refresh();
        this.bottom();
      }
    } catch {
      this.error.set("Message was not sent. Your draft is retained.");
    } finally {
      this.sending.set(false);
    }
  }

  private bottom() {
    requestAnimationFrame(() => {
      const element = this.scroll?.nativeElement;
      if (element) element.scrollTop = element.scrollHeight;
    });
  }

  ngOnDestroy() {
    this.destroyed = true;
    clearInterval(this.timer);
  }
}
