import { ChatService } from "../chat-panel/chat.service";
import { SessionService } from "../../core/session.service";
import { UsersService } from "../../core/users.service";
import { CommitmentsService } from "../../features/commitments/commitments.service";
import {
  Component,
  inject,
  signal,
  effect,
  OnDestroy,
  HostListener,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Api } from "../../core/api.service";
import { Panels } from "../../core/panels.service";
import { Commitment, User } from "../../core/models";
import { DependencyGraph } from "../dependency-graph/dependency-graph.component";
@Component({
  selector: "commitment-drawer",
  standalone: true,
  imports: [FormsModule, DatePipe, DependencyGraph],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./commitment-drawer.component.html",
  styleUrl: "./commitment-drawer.component.scss",
})
export class CommitmentDrawer implements OnDestroy {
  chatData = inject(ChatService);

  session = inject(SessionService);
  directory = inject(UsersService);
  commitmentData = inject(CommitmentsService);

  api = inject(Api);
  panels = inject(Panels);
  item = signal<Commitment | null>(null);
  candidates = signal<Commitment[]>([]);
  loadError = signal("");
  analysisError = signal("");
  analyzing = signal(false);
  saving = signal(false);
  drafting = signal(false);
  sending = signal(false);
  analyzedRevision = "";
  draft = "";
  recipientId = "";
  dirty = false;
  prerequisite = "";
  replacements: Record<string, string> = {};
  edit = {
    title: "",
    owner_id: "",
    due_date: "",
    status: "active",
    progress: 0,
    condition: "",
    condition_met: false,
    blocker: "",
  };
  private current = "";
  private epoch = 0;
  private fetching = false;
  private previousFocus: HTMLElement | null = null;
  private timer: ReturnType<typeof setInterval>;
  constructor() {
    effect(() => {
      const id = this.panels.commitment();
      this.api.revision();
      if (!id) {
        this.current = "";
        this.epoch++;
        this.item.set(null);
        document.body.style.overflow = "";
        this.previousFocus?.focus();
        return;
      }
      if (id !== this.current) {
        this.current = id;
        this.epoch++;
        this.item.set(null);
        this.dirty = false;
        this.draft = "";
        this.recipientId = "";
        this.analyzedRevision = "";
        this.analysisError.set("");
        this.replacements = {};
        this.previousFocus = document.activeElement as HTMLElement;
        document.body.style.overflow = "hidden";
        setTimeout(
          () => document.getElementById("commitment-drawer")?.focus(),
          0,
        );
        void this.prepare();
      }
      void this.load();
    });
    this.timer = setInterval(() => {
      if (this.current && !this.saving()) void this.load();
    }, 5000);
  }
  async prepare() {
    const epoch = this.epoch;
    try {
      await this.directory.loadUsers();
      const rows = await this.commitmentData.commitments();
      if (epoch === this.epoch) this.candidates.set(rows);
    } catch {}
  }
  async load() {
    const id = this.current,
      epoch = this.epoch;
    if (!id || this.fetching) return;
    this.fetching = true;
    try {
      const c = await this.commitmentData.get(id);
      if (epoch !== this.epoch) return;
      this.item.set(c);
      this.loadError.set("");
      if (!this.recipientId) {
        this.recipientId =
          c.owner_id !== this.session.user()?.id
            ? c.owner_id || ""
            : c.related?.find(
                (x) =>
                  c.dependencies.includes(x.id) &&
                  x.owner_id !== this.session.user()?.id,
              )?.owner_id || "";
      }
      if (!this.dirty)
        this.edit = {
          title: c.title,
          owner_id: c.owner_id || "",
          due_date: c.due_date || "",
          status: c.status,
          progress: c.progress,
          condition: c.condition,
          condition_met: c.condition_met,
          blocker: c.blocker,
        };
      if (
        c.analysis?.stale &&
        this.analyzedRevision !== c.analysis.revision &&
        !this.analyzing()
      )
        void this.refreshAnalysis();
    } catch (e) {
      if (epoch === this.epoch)
        this.loadError.set(
          "Commitment could not load. It may have been deleted.",
        );
    } finally {
      this.fetching = false;
      if (epoch !== this.epoch && this.current) void this.load();
    }
  }
  async refreshAnalysis() {
    const c = this.item();
    if (!c || this.analyzing()) return;
    const id = c.id,
      epoch = this.epoch;
    this.analyzedRevision = c.analysis?.revision || "";
    this.analyzing.set(true);
    this.analysisError.set("");
    try {
      await this.commitmentData.analyze(id);
      if (epoch === this.epoch) await this.load();
    } catch (e) {
      if (epoch === this.epoch) {
        const detail = (e as { error?: { detail?: string } }).error?.detail;
        this.analysisError.set(
          detail || "AI explanation unavailable; retry manually.",
        );
      }
    } finally {
      this.analyzing.set(false);
    }
  }
  owner(c: Commitment) {
    return this.directory.users().find((u) => u.id === c.owner_id);
  }
  name(id: string) {
    return (
      this.item()?.related?.find((x) => x.id === id)?.title ||
      this.candidates().find((x) => x.id === id)?.title ||
      id
    );
  }
  async save() {
    const id = this.current;
    this.saving.set(true);
    try {
      await this.commitmentData.update(id, {
        ...this.edit,
        progress: Number(this.edit.progress),
        due_date: this.edit.due_date || null,
      });
      this.dirty = false;
      this.api.changed();
      await this.load();
      await this.prepare();
    } catch {
    } finally {
      this.saving.set(false);
    }
  }
  async mutation(path: string, method: string, body?: unknown) {
    this.saving.set(true);
    try {
      await this.commitmentData.dependencyMutation(method, path, body);
      this.prerequisite = "";
      this.replacements = {};
      this.api.changed();
      await this.load();
      await this.prepare();
    } catch {
    } finally {
      this.saving.set(false);
    }
  }
  add() {
    return this.mutation(`/commitments/${this.current}/dependencies`, "POST", {
      prerequisite_id: this.prerequisite,
    });
  }
  remove(id: string) {
    return this.mutation(
      `/commitments/${this.current}/dependencies/${id}`,
      "DELETE",
    );
  }
  replace(id: string) {
    return this.mutation(
      `/commitments/${this.current}/dependencies/${id}/replace`,
      "POST",
      { prerequisite_id: this.replacements[id] },
    );
  }
  async followup() {
    const id = this.current,
      epoch = this.epoch;
    this.drafting.set(true);
    try {
      const r = await this.commitmentData.followup(id, this.recipientId);
      if (epoch === this.epoch) {
        this.draft = r.message;
        await this.load();
      }
    } catch {
    } finally {
      this.drafting.set(false);
    }
  }
  async sendFollowup() {
    const c = this.item(),
      body = this.draft.trim();
    if (!c || !this.recipientId || !body) return;
    const owner = this.directory.users().find((u) => u.id === this.recipientId);
    if (!owner) return;
    this.sending.set(true);
    try {
      await this.chatData.send(owner.id, body, c.id);
      this.draft = "";
      this.panels.close();
      this.panels.chat(owner);
      this.api.changed();
    } catch {
    } finally {
      this.sending.set(false);
    }
  }
  openChat(c: Commitment) {
    const owner = this.directory.users().find((u) => u.id === this.recipientId);
    if (owner) {
      this.panels.close();
      this.panels.chat(owner);
    }
  }
  @HostListener("document:keydown", ["$event"]) key(event: KeyboardEvent) {
    if (!this.current) return;
    if (event.key === "Escape") {
      this.panels.close();
      return;
    }
    if (event.key === "Tab") {
      const el = document.getElementById("commitment-drawer");
      const controls = el?.querySelectorAll<HTMLElement>(
        'button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]',
      );
      if (!controls?.length) return;
      const first = controls[0],
        last = controls[controls.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === el)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
  ngOnDestroy() {
    clearInterval(this.timer);
    this.epoch++;
    document.body.style.overflow = "";
  }
}
