import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { Meeting } from "../../core/models";
export interface DeletionPreview {
  meeting_id: string;
  meeting_title: string;
  commitment_ids: string[];
  commitment_count: number;
  dependency_count: number;
  event_count: number;
  commitments: { id: string; title: string; owner: string; direct: boolean }[];
  other_meetings: { id: string; title: string }[];
}
@Injectable({ providedIn: "root" })
export class MeetingsService {
  private api = inject(Api);
  list(): Promise<Meeting[]> {
    return this.api.call("GET", "/meetings");
  }
  create(
    title: string,
    heldOn: string,
    transcript: string,
    visibility: "public" | "private",
    participantIds: string[],
  ): Promise<Meeting> {
    return this.api.call("POST", "/meetings", {
      title,
      held_on: heldOn,
      transcript,
      visibility,
      participant_ids: participantIds,
    });
  }
  analyze(id: string): Promise<Meeting> {
    return this.api.call("POST", `/meetings/${id}/analyze`);
  }
  review(id: string, items: unknown[]): Promise<Meeting> {
    return this.api.call("POST", `/meetings/${id}/review`, { items });
  }
  deletionPreview(id: string): Promise<DeletionPreview> {
    return this.api.call("GET", `/meetings/${id}/deletion-preview`);
  }
  delete(id: string, expected: string[]): Promise<unknown> {
    return this.api.call("DELETE", `/meetings/${id}`, {
      expected_commitment_ids: expected,
    });
  }
}
