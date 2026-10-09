import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from "@angular/core";
import { DatePipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ChatMessage, User } from "../../core/models";
import { SessionService } from "../../core/session.service";
import { UsersService } from "../../core/users.service";
import { ChatService } from "../../shared/chat-panel/chat.service";

@Component({
  selector: "app-chat",
  standalone: true,
  imports: [FormsModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./chat.component.html",
  styleUrl: "./chat.component.scss",
})
export class Chat {
  readonly session = inject(SessionService);

  private readonly usersService = inject(UsersService);
  private readonly chatService = inject(ChatService);
  private readonly destroyRef = inject(DestroyRef);

  readonly search = signal("");
  readonly peer = signal<User | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly draft = signal("");
  readonly error = signal("");
  readonly directoryLoading = signal(true);
  readonly loading = signal(false);
  readonly sending = signal(false);
  readonly loadingOlder = signal(false);
  readonly hasMore = signal(false);

  readonly users = computed(() => {
    const query = this.search().trim().toLowerCase();
    const currentId = this.session.user()?.id;

    return this.usersService.users()
      .filter(user =>
        user.active &&
        user.id !== currentId &&
        `${user.name} ${user.email} ${user.team}`
          .toLowerCase()
          .includes(query)
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  });

  private generation = 0;
  private before: string | null = null;
  private refreshing = false;
  private destroyed = false;

  constructor() {
    void this.loadUsers();

    const timer = setInterval(() => {
      if (!document.hidden) void this.refresh();
    }, 5000);

    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
      this.generation++;
      clearInterval(timer);
    });
  }

  async loadUsers(): Promise<void> {
    this.directoryLoading.set(true);

    try {
      await this.usersService.loadUsers();
    } catch {
      if (!this.destroyed) {
        this.error.set("Could not load users. Please retry.");
      }
    } finally {
      if (!this.destroyed) this.directoryLoading.set(false);
    }
  }

  async selectUser(user: User): Promise<void> {
    if (this.peer()?.id === user.id) return;

    const generation = ++this.generation;

    this.peer.set(user);
    this.messages.set([]);
    this.draft.set("");
    this.error.set("");
    this.hasMore.set(false);
    this.before = null;
    this.loading.set(true);

    try {
      const page = await this.chatService.list(user.id);

      if (generation !== this.generation) return;

      this.messages.set(page.items);
      this.before = page.before;
      this.hasMore.set(page.has_more);
    } catch {
      if (generation === this.generation) {
        this.error.set("Could not load this conversation.");
      }
    } finally {
      if (generation === this.generation) this.loading.set(false);
    }
  }

  private merge(items: ChatMessage[]): void {
    this.messages.update(current => {
      const indexed = new Map(
        current.map(message => [message.id, message])
      );

      for (const message of items) indexed.set(message.id, message);

      return [...indexed.values()].sort((a, b) =>
        a.created_at.localeCompare(b.created_at) ||
        a.id.localeCompare(b.id)
      );
    });
  }

  async refresh(): Promise<void> {
    const user = this.peer();

    if (
      !user ||
      this.destroyed ||
      this.refreshing ||
      this.loading() ||
      this.loadingOlder()
    ) return;

    const generation = this.generation;
    this.refreshing = true;

    try {
      const page = await this.chatService.list(user.id);

      if (generation !== this.generation) return;

      this.merge(page.items);

      // Initialise pagination after an initial loading failure.
      if (!this.before) {
        this.before = page.before;
        this.hasMore.set(page.has_more);
      }
    } catch {
      // Keep existing messages visible during temporary polling failures.
    } finally {
      this.refreshing = false;
    }
  }

  async loadOlder(): Promise<void> {
    const user = this.peer();
    const cursor = this.before;

    if (!user || !cursor || this.loadingOlder()) return;

    const generation = this.generation;
    this.loadingOlder.set(true);
    this.error.set("");

    try {
      const page = await this.chatService.list(user.id, cursor);

      if (generation !== this.generation) return;

      this.merge(page.items);
      this.before = page.before;
      this.hasMore.set(page.has_more);
    } catch {
      if (generation === this.generation) {
        this.error.set("Could not load older messages.");
      }
    } finally {
      if (generation === this.generation) {
        this.loadingOlder.set(false);
      }
    }
  }

  async send(): Promise<void> {
    const user = this.peer();
    const text = this.draft().trim();

    if (!user || !text || this.sending() || this.loading()) return;

    const generation = this.generation;
    const originalDraft = this.draft();

    this.sending.set(true);
    this.error.set("");

    try {
      const message = await this.chatService.send(
        user.id,
        text,
        undefined,
        true,
      );

      if (generation !== this.generation) return;

      this.merge([message]);

      // Preserve anything typed while the request was running.
      if (this.draft() === originalDraft) this.draft.set("");
    } catch {
      if (generation === this.generation) {
        this.error.set(
          "Sending could not be confirmed. Refresh before retrying."
        );
      }
    } finally {
      if (!this.destroyed) this.sending.set(false);
    }
  }
}