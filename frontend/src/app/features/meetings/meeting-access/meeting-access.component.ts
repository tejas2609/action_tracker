import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  output,
  signal,
  untracked,
} from "@angular/core";
import { FormsModule } from "@angular/forms";

import { Api } from "../../../core/api.service";
import { SessionService } from "../../../core/session.service";
import {
  AccessRequest,
  DirectoryMeeting,
  MeetingAccessService,
} from "./meeting-access.service";

@Component({
  selector: "app-meeting-access",
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./meeting-access.component.html",
  styleUrl: "./meeting-access.component.scss",
})
export class MeetingAccessComponent {
  private data = inject(MeetingAccessService);
  private api = inject(Api);

  session = inject(SessionService);
  openMeeting = output<string>();

  query = "";
  searchQuery = signal("");
  page = signal(1);
  inboxPage = signal(1);

  meetings = signal<DirectoryMeeting[]>([]);
  requests = signal<AccessRequest[]>([]);
  total = signal(0);
  inboxTotal = signal(0);

  loading = signal(false);
  inboxLoading = signal(false);
  busyId = signal("");
  error = signal("");
  inboxError = signal("");

  reasons: Record<string, string> = {};

  private directoryToken = 0;
  private inboxToken = 0;
  private destroyed = false;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      this.directoryToken++;
      this.inboxToken++;
    });

    effect(() => {
      const q = this.searchQuery();
      const page = this.page();
      this.api.revision();

      untracked(() => {
        void this.loadDirectory(q, page);
      });
    });

    effect(() => {
      const manager = this.session.user()?.is_manager;
      const page = this.inboxPage();
      this.api.revision();

      untracked(() => {
        if (manager) {
          void this.loadInbox(page);
        } else {
          this.requests.set([]);
        }
      });
    });
  }

  private message(error: unknown, fallback: string): string {
    const response = error as {
      error?: { detail?: unknown };
    };

    return typeof response?.error?.detail === "string"
      ? response.error.detail
      : fallback;
  }

  search() {
    this.page.set(1);
    this.searchQuery.set(this.query.trim());

    // Also refresh when the same query is submitted again.
    void this.loadDirectory(this.query.trim(), 1);
  }

  refresh() {
    void this.loadDirectory(this.searchQuery(), this.page());

    if (this.session.user()?.is_manager) {
      void this.loadInbox(this.inboxPage());
    }

    this.api.changed();
  }

  private async loadDirectory(q: string, page: number) {
    const token = ++this.directoryToken;
    this.loading.set(true);

    try {
      const result = await this.data.directory(q, page);

      if (this.destroyed || token !== this.directoryToken) return;

      this.meetings.set(result.items);
      this.total.set(result.total);
    } catch (error: unknown) {
      if (!this.destroyed && token === this.directoryToken) {
        this.error.set(
          this.message(error, "Unable to load meeting directory."),
        );
      }
    } finally {
      if (!this.destroyed && token === this.directoryToken) {
        this.loading.set(false);
      }
    }
  }

  private async loadInbox(page: number) {
    const token = ++this.inboxToken;
    this.inboxLoading.set(true);

    try {
      const result = await this.data.inbox(page);

      if (this.destroyed || token !== this.inboxToken) return;

      this.requests.set(result.items);
      this.inboxTotal.set(result.total);
    } catch (error: unknown) {
      if (!this.destroyed && token === this.inboxToken) {
        this.inboxError.set(
          this.message(error, "Unable to load access requests."),
        );
      }
    } finally {
      if (!this.destroyed && token === this.inboxToken) {
        this.inboxLoading.set(false);
      }
    }
  }

  async requestAccess(meeting: DirectoryMeeting) {
    if (this.busyId()) return;

    this.busyId.set(meeting.id);
    this.error.set("");

    try {
      await this.data.request(
        meeting.id,
        this.reasons[meeting.id] || "",
      );

      this.api.changed();
    } catch (error: unknown) {
      this.error.set(
        this.message(error, "Could not request access."),
      );
    } finally {
      this.busyId.set("");
    }
  }

  async decide(
    request: AccessRequest,
    decision: "approved" | "rejected",
  ) {
    if (this.busyId()) return;

    this.busyId.set(request.id);
    this.inboxError.set("");

    try {
      await this.data.decide(request.id, decision);
      this.api.changed();
    } catch (error: unknown) {
      this.inboxError.set(
        this.message(error, "Could not save the decision."),
      );
    } finally {
      this.busyId.set("");
    }
  }
}