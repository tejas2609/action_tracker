import { Injectable, inject } from "@angular/core";
import { Api } from "../../../core/api.service";

export interface DirectoryMeeting {
  id: string;
  title: string;
  held_on: string;
  can_access: boolean;
  request_status: "pending" | "approved" | "rejected" | null;
}

export interface AccessRequest {
  id: string;
  meeting_id: string;
  meeting_title: string;
  requester_name: string;
  reason: string;
  created_at: string;
}

export interface AccessPage<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

@Injectable({ providedIn: "root" })
export class MeetingAccessService {
  private api = inject(Api);

  directory(
    q: string,
    page: number,
  ): Promise<AccessPage<DirectoryMeeting>> {
    const params = new URLSearchParams({
      q,
      page: String(page),
      page_size: "10",
    });

    return this.api.call(
      "GET",
      `/meeting-directory?${params}`,
      undefined,
      true,
    );
  }

  request(meetingId: string, reason: string): Promise<unknown> {
    return this.api.call(
      "POST",
      `/meetings/${encodeURIComponent(meetingId)}/access-requests`,
      { reason },
      true,
    );
  }

  inbox(
    page: number,
  ): Promise<AccessPage<AccessRequest>> {
    return this.api.call(
      "GET",
      `/meeting-access-requests?page=${page}&page_size=10`,
      undefined,
      true,
    );
  }

  decide(
    id: string,
    decision: "approved" | "rejected",
  ): Promise<unknown> {
    return this.api.call(
      "POST",
      `/meeting-access-requests/${encodeURIComponent(id)}/decision`,
      { decision },
      true,
    );
  }
}