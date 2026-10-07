import { ChatService } from "./chat.service";
import { SessionService } from "../../core/session.service";
import {
  Component,
  inject,
  signal,
  effect,
  OnDestroy,
  ViewChild,
  ElementRef,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Api } from "../../core/api.service";
import { Panels } from "../../core/panels.service";
import { ChatMessage, ChatPage, User } from "../../core/models";
@Component({
  selector: "chat-panel",
  standalone: true,
  imports: [FormsModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./chat-panel.component.html",
  styleUrl: "./chat-panel.component.scss",
})
export class ChatPanel implements OnDestroy {
  chatData = inject(ChatService);

  session = inject(SessionService);
  api = inject(Api);
  panels = inject(Panels);
  messages = signal<ChatMessage[]>([]);
  hasMore = signal(false);
  before: string | null = null;
  error = signal("");
  sending = signal(false);
  draft = "";
  private peerId = "";
  private timer: ReturnType<typeof setInterval>;
  private request = 0;
  @ViewChild("scrollArea") scroll?: ElementRef<HTMLElement>;
  constructor() {
    effect(() => {
      const peer = this.panels.peer();
      this.peerId = peer?.id || "";
      this.request++;
      this.messages.set([]);
      this.hasMore.set(false);
      this.before = null;
      this.draft = "";
      this.error.set("");
      if (peer) void this.load(peer, false);
    });
    this.timer = setInterval(() => {
      const peer = this.panels.peer();
      if (peer) void this.load(peer, true);
    }, 3000);
  }
  async load(peer: User, poll: boolean) {
    const epoch = this.request;
    try {
      const r = await this.chatData.list(peer.id);
      if (epoch !== this.request) return;
      const previous = this.messages();
      const known = new Map(previous.map((m) => [m.id, m]));
      r.items.forEach((m) => known.set(m.id, m));
      const next = [...known.values()].sort(
        (a, b) =>
          a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id),
      );
      const newMessages = next.length > previous.length;
      this.messages.set(next);
      if (!poll) {
        this.hasMore.set(r.has_more);
        this.before = r.before;
      }
      this.error.set("");
      if (newMessages && !poll) this.bottom();
    } catch {
      if (epoch === this.request)
        this.error.set("Messages could not load. Retrying automatically.");
    }
  }
  async older() {
    const peer = this.panels.peer();
    if (!peer || !this.before) return;
    const epoch = this.request;
    try {
      const r = await this.chatData.list(peer.id, this.before);
      if (epoch !== this.request) return;
      const merged = new Map(
        [...r.items, ...this.messages()].map((m) => [m.id, m]),
      );
      this.messages.set(
        [...merged.values()].sort(
          (a, b) =>
            a.created_at.localeCompare(b.created_at) ||
            a.id.localeCompare(b.id),
        ),
      );
      this.before = r.before;
      this.hasMore.set(r.has_more);
    } catch {
      this.error.set("Could not load older messages.");
    }
  }
  async send() {
    const peer = this.panels.peer(),
      body = this.draft.trim();
    if (!peer || !body || this.sending()) return;
    this.sending.set(true);
    try {
      await this.chatData.send(peer.id, body, undefined, true);
      if (this.panels.peer()?.id === peer.id) {
        this.draft = "";
        await this.load(peer, false);
        this.bottom();
      }
    } catch {
      this.error.set("Message was not sent. Your draft is retained; retry.");
    } finally {
      this.sending.set(false);
    }
  }
  bottom() {
    setTimeout(() => {
      const el = this.scroll?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    }, 30);
  }
  ngOnDestroy() {
    clearInterval(this.timer);
    this.request++;
  }
}
