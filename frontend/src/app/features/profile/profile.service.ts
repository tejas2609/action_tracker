import { Injectable, inject } from "@angular/core";
import { Api } from "../../core/api.service";
import { User } from "../../core/models";
export interface ProfileData {
  user: User;
  manager: User | null;
  members: User[];
  available: User[];
}
@Injectable({ providedIn: "root" })
export class ProfileService {
  private api = inject(Api);
  load(): Promise<ProfileData> {
    return this.api.call("GET", "/profile");
  }
  save(body: { name: string; email: string }): Promise<ProfileData> {
    return this.api.call("PATCH", "/profile", body);
  }
  add(userId: string): Promise<ProfileData> {
    return this.api.call("POST", "/profile/team/" + encodeURIComponent(userId));
  }
  remove(userId: string): Promise<ProfileData> {
    return this.api.call(
      "DELETE",
      "/profile/team/" + encodeURIComponent(userId),
    );
  }
}
