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

@Component({
  standalone: true,
  imports: [FormsModule],
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
  heldOn = new Date().toISOString().slice(0, 10);
  transcript = "";
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
    try {
      const m = await this.meetingData.create(
        this.title,
        this.heldOn,
        this.transcript,
      );
      await this.load();
      this.select(m);
      await this.analyze(m.id);
    } catch {}
  }
  async analyze(id: string) {
    try {
      this.select(await this.meetingData.analyze(id));
      await this.load();
    } catch {}
  }
  assign(f: Meeting["findings"][number], id: string) {
    f.owner = this.directory.users().find((u) => u.id === id)?.name || f.owner;
  }
  async review(m: Meeting) {
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
      this.api.error.set(
        "Add an owner and promise; choose an existing commitment for every link.",
      );
      return;
    }
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
    } catch {}
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
      this.api.changed();
      await this.load();
    } catch {
      this.deletion.set(null);
    }
  }
}
