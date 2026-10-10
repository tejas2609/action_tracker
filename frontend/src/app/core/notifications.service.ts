import {
  DestroyRef,
  Injectable,
  effect,
  inject,
  signal,
} from "@angular/core";

import { Api } from "./api.service";
import { SessionService } from "./session.service";

export interface AppNotification {
  id: string;
  kind: "chat" | "commitment_created" | "commitment_review";
  title: string;
  peer_id: string | null;
  commitment_id: string | null;
  created_at: string;
  read_at: string | null;
}

interface NotificationSnapshot {
  type: "notifications";
  unread_count: number;
  items: AppNotification[];
}

@Injectable({ providedIn: "root" })
export class NotificationsService {
  private api = inject(Api);
  private session = inject(SessionService);
  private destroyRef = inject(DestroyRef);

  readonly items = signal<AppNotification[]>([]);
  readonly unread = signal(0);
  readonly connected = signal(false);
  readonly loading = signal(false);
  readonly loaded = signal(false);
  readonly error = signal("");

  private socket: WebSocket | null = null;
  private retryTimer?: ReturnType<typeof setTimeout>;
  private generation = 0;
  private retryDelay = 1000;
  private snapshotRevision = 0;
  private request = 0;

  constructor() {
    effect(() => {
      const user = this.session.user();

      this.disconnect();

      this.items.set([]);
      this.unread.set(0);
      this.error.set("");
      this.loading.set(false);
      this.loaded.set(false);

      if (user && this.session.token) {
        void this.refresh();
        this.connect(this.generation);
      }
    });

    this.destroyRef.onDestroy(() => this.disconnect());
  }

  async refresh(): Promise<void> {
    const generation = this.generation;
    const userId = this.session.user()?.id;
    const token = this.session.token;
    if (!userId || !token) return;
    const request = ++this.request;
    const revision = this.snapshotRevision;
    const current = () =>
      generation === this.generation && request === this.request &&
      userId === this.session.user()?.id && token === this.session.token;

    this.loading.set(true);
    try {
      const data = await this.api.call<NotificationSnapshot>(
        "GET", "/notifications", undefined, true,
      );
      // A live snapshot received during this request is newer than its response.
      if (!current() || revision !== this.snapshotRevision) return;
      this.items.set(data.items);
      this.unread.set(data.unread_count);
      this.loaded.set(true);
      this.error.set("");
    } catch {
      if (current() && revision === this.snapshotRevision)
        this.error.set("Notifications could not load. Please retry.");
    } finally {
      if (current()) this.loading.set(false);
    }
  }

  private connect(generation: number) {
    const token = this.session.token;

    if (!token || generation !== this.generation) return;

    const url = new URL(
      "/api/notifications/ws",
      window.location.origin,
    );

    url.protocol = location.protocol === "https:" ? "wss:" : "ws:";

    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      if (generation !== this.generation) {
        socket.close();
        return;
      }

      socket.send(JSON.stringify({
        type: "auth",
        token,
      }));
    };

    socket.onmessage = event => {
      if (generation !== this.generation) return;

      try {
        const data = JSON.parse(event.data) as NotificationSnapshot;

        if (
          data.type !== "notifications" ||
          !Array.isArray(data.items) ||
          typeof data.unread_count !== "number"
        ) {
          return;
        }

        ++this.snapshotRevision;
        this.items.set(data.items);
        this.unread.set(data.unread_count);
        this.connected.set(true);
        this.loaded.set(true);
        this.error.set("");
        this.retryDelay = 1000;
      } catch {
        socket.close();
      }
    };

    socket.onerror = () => socket.close();

    socket.onclose = event => {
      if (generation !== this.generation) return;

      this.socket = null;
      this.connected.set(false);

      if (event.code === 1008) {
        this.error.set(
          "Live notifications unavailable. Check your session and connection settings.",
        );
        return;
      }

      if (!this.session.user() || !this.session.token) return;

      this.error.set("Reconnecting live notifications…");

      const delay = this.retryDelay + Math.random() * 500;
      this.retryDelay = Math.min(this.retryDelay * 2, 30000);

      this.retryTimer = setTimeout(
        () => this.connect(generation),
        delay,
      );
    };
  }

  private disconnect() {
    ++this.generation;

    clearTimeout(this.retryTimer);
    this.retryTimer = undefined;

    const socket = this.socket;
    this.socket = null;

    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socket.close();
    }

    this.connected.set(false);
    this.retryDelay = 1000;
  }

  async markRead(id: string): Promise<{ ok: boolean }> {
    const generation = this.generation;
    const userId = this.session.user()?.id;
    const token = this.session.token;
    const result = await this.api.call<{ ok: boolean }>(
      "POST",
      `/notifications/${encodeURIComponent(id)}/read`,
      {},
      true,
    );
    if (
      generation === this.generation && userId === this.session.user()?.id &&
      token === this.session.token
    ) await this.refresh();
    return result;
  }
}
