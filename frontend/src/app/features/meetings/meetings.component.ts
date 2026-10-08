import { DeletionPreview } from "./meetings.service";
import { MeetingsService } from "./meetings.service";
import { UsersService } from "../../core/users.service";
import { CommitmentsService } from "../commitments/commitments.service";
import {
  Component,
  inject,
  signal,
  OnInit,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Api } from "../../core/api.service";
import { Meeting, Commitment } from "../../core/models";
import { A11yModule } from "@angular/cdk/a11y";
import { MeetingActionTracker } from "./action-tracker/action-tracker.component";
import { MeetingAccessComponent } from "./meeting-access/meeting-access.component";

@Component({
  standalone: true,
  imports: [
    FormsModule,
    A11yModule,
    MeetingActionTracker,
    MeetingAccessComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./meetings.component.html",
  styleUrl: "./meetings.component.scss",
})
export class Meetings implements OnInit {
  meetingData = inject(MeetingsService);

  directory = inject(UsersService);
  commitmentData = inject(CommitmentsService);

  deletion = signal<DeletionPreview | null>(null);
  api = inject(Api);
  meetings = signal<Meeting[]>([]);
  commitments = signal<Commitment[]>([]);
  selected = signal<Meeting | null>(null);
  title = "";
  heldOn = this.today();
  transcript = "";

  showCreate = signal(false);
  showReview = signal(false);

  creating = signal(false);
  analyzing = signal(false);
  reviewSaving = signal(false);

  createError = signal("");
  reviewError = signal("");

  visibility: "public" | "private" = "public";
  participantIds: string[] = [];

  private today(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
  }

  private errorMessage(error: unknown, fallback: string): string {
    const response = error as {
      error?: { detail?: unknown };
    };

    return typeof response?.error?.detail === "string"
      ? response.error.detail
      : fallback;
  }

  async ngOnInit() {
    await this.load();
  }
  async load() {
    try {
      await this.directory.loadUsers();
      this.meetings.set(await this.meetingData.list());
      this.commitments.set(await this.commitmentData.commitments());
    } catch {}
  }
  select(m: Meeting) {
    this.deletion.set(null);
    this.selected.set({
      ...m,
      findings: m.findings.map((f) => ({
        ...f,
        owner_id:
          f.owner_id ||
          this.directory
            .users()
            .find((u) => u.name.toLowerCase() === f.owner.toLowerCase())?.id ||
          null,
        depends_on_indices: f.depends_on_indices || [],
        prerequisite_ids: f.prerequisite_ids || [],
        action: f.existing_id
          ? "link"
          : f.kind === "commitment"
            ? "confirm"
            : "ignore",
      })),
    });
  }
  example() {
    this.title = "Launch readiness";
    this.transcript = `Sarah: I'll finish the QA report by tomorrow.
Alex: I'll deploy the release once QA approves the build.
Priya: We could consider a new landing page next quarter.
Alex: Could Sarah review the deployment checklist?
Sarah: I'll review the deployment checklist by tomorrow.`;
  }
  async create() {
    if (this.creating()) return;

    const title = this.title.trim();
    const transcript = this.transcript.trim();

    if (!title || !this.heldOn || transcript.length < 10) {
      this.createError.set(
        "Enter a title, meeting date, and transcript of at least 10 characters.",
      );
      return;
    }

    this.creating.set(true);
    this.createError.set("");

    let saved: Meeting;

    try {
      saved = await this.meetingData.create(
        title,
        this.heldOn,
        transcript,
        this.visibility,
        this.participantIds,
      );
    } catch (error: unknown) {
      this.createError.set(
        this.errorMessage(error, "Could not save the meeting. Please retry."),
      );
      return;
    } finally {
      this.creating.set(false);
    }

    // Reset only after saving succeeds.
    this.showCreate.set(false);
    this.resetCreateForm();

    this.select(saved);
    this.reviewError.set("");
    this.showReview.set(true);

    // Show the saved meeting immediately in history.
    this.meetings.update((items) => [
      saved,
      ...items.filter((item) => item.id !== saved.id),
    ]);
    this.api.changed();

    await this.analyze(saved.id);
  }

  async analyze(id: string) {
    if (this.analyzing()) return;

    this.analyzing.set(true);
    this.reviewError.set("");

    try {
      const analyzed = await this.meetingData.analyze(id);

      this.meetings.update((items) =>
        items.map((item) => (item.id === analyzed.id ? analyzed : item)),
      );

      // Do not reopen the drawer if the user closed it during analysis.
      if (this.selected()?.id === id) {
        this.select(analyzed);
      }

      this.api.changed();
      await this.load();
    } catch (error: unknown) {
      this.reviewError.set(
        this.errorMessage(
          error,
          "The meeting is saved, but analysis failed. Click Analyze to retry.",
        ),
      );
    } finally {
      this.analyzing.set(false);
    }
  }
  assign(f: Meeting["findings"][number], id: string) {
    f.owner = this.directory.users().find((u) => u.id === id)?.name || f.owner;
  }
  async review(m: Meeting) {
    if (this.reviewSaving() || this.analyzing()) return;

    this.reviewError.set("");

    if (
      m.findings.some(
        (f) =>
          f.action !== "ignore" &&
          (!f.owner_id ||
            !f.owner.trim() ||
            !f.title.trim() ||
            (f.action === "link" && !f.existing_id)),
      )
    ) {
      this.reviewError.set(
        "Add an owner and promise; choose an existing commitment for every link.",
      );
      return;
    }

    this.reviewSaving.set(true);

    try {
      const result = await this.meetingData.review(
        m.id,
        m.findings.map((f, index) => ({
          index,
          action: f.action,
          title: f.title || "Ignored",
          owner: f.owner || "Unknown",
          owner_id: f.owner_id,
          due_date: f.due_date || null,
          condition: f.condition,
          existing_id: f.existing_id,
          depends_on_indices: f.depends_on_indices,
          prerequisite_ids: f.prerequisite_ids,
        })),
      );

      this.select(result);
      this.api.changed();
      await this.load();
    } catch (error: unknown) {
      this.reviewError.set(
        this.errorMessage(error, "Could not save the review. Please retry."),
      );
    } finally {
      this.reviewSaving.set(false);
    }
  }
  async previewDelete(m: Meeting) {
    try {
      this.deletion.set(await this.meetingData.deletionPreview(m.id));
    } catch {}
  }
  async confirmDelete() {
    const preview = this.deletion();
    if (!preview) return;
    try {
      await this.meetingData.delete(preview.meeting_id, preview.commitment_ids);
      this.deletion.set(null);
      this.selected.set(null);
      this.showReview.set(false);
      this.api.changed();
      await this.load();
    } catch {
      this.deletion.set(null);
    }
  }

  openCreate() {
    if (this.creating() || this.analyzing() || this.reviewSaving()) return;

    this.showReview.set(false);
    this.createError.set("");
    this.showCreate.set(true);
  }

  closeCreate() {
    if (this.creating()) return;
    this.showCreate.set(false);
  }

  openReview(m: Meeting) {
    if (this.creating() || this.analyzing() || this.reviewSaving()) return;

    this.showCreate.set(false);
    this.reviewError.set("");

    // Preserve unsaved review edits when reopening the same meeting.
    if (this.selected()?.id !== m.id) {
      this.select(m);
    }

    this.showReview.set(true);
  }

  closeReview() {
    if (this.reviewSaving()) return;

    this.deletion.set(null);
    this.showReview.set(false);

    // Keep selected() so closing does not discard review edits.
  }

  private resetCreateForm() {
    this.title = "";
    this.heldOn = this.today();
    this.transcript = "";
    this.visibility = "public";
    this.participantIds = [];
  }

  async openDirectoryMeeting(id: string) {
    if (this.creating() || this.analyzing() || this.reviewSaving()) {
      return;
    }

    await this.load();

    const meeting = this.meetings().find((item) => item.id === id);

    if (meeting) {
      this.openReview(meeting);
    } else {
      this.api.error.set(
        "Meeting access is unavailable. Refresh and try again.",
      );
    }
  }
}
