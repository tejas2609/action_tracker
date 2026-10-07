import { ProfileData } from "./profile.service";
import { ProfileService } from "./profile.service";
import { SessionService } from "../../core/session.service";
import { UsersService } from "../../core/users.service";
import {
  Component,
  inject,
  signal,
  OnInit,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";

import { Api } from "../../core/api.service";
import { User } from "../../core/models";

@Component({
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./profile.component.html",
  styleUrl: "./profile.component.scss",
})
export class Profile implements OnInit {
  profileData = inject(ProfileService);

  session = inject(SessionService);
  directory = inject(UsersService);

  api = inject(Api);

  data = signal<ProfileData | null>(null);
  working = signal(false);
  message = signal("");

  name = "";
  email = "";
  selectedUser = "";

  async ngOnInit(): Promise<void> {
    try {
      const result = await this.profileData.load();
      this.apply(result);
    } catch {
      // Api.call already exposes the error.
    }
  }

  private apply(result: ProfileData): void {
    this.data.set(result);
    this.session.user.set(result.user);
    this.name = result.user.name;
    this.email = result.user.email;
    this.selectedUser = "";
  }

  private async mutate(
    operation: () => Promise<ProfileData>,
    success = "Saved.",
  ): Promise<void> {
    if (this.working()) return;

    this.working.set(true);
    this.message.set("");

    try {
      const result = await operation();

      this.apply(result);
      this.api.changed();
      this.message.set(success);

      try {
        await this.directory.loadUsers();
      } catch {
        this.api.error.set(
          "Changes saved, but the user directory could not refresh.",
        );
      }
    } catch {
      // Keep the current page and display the backend error.
    } finally {
      this.working.set(false);
    }
  }

  async save(): Promise<void> {
    await this.mutate(
      () =>
        this.profileData.save({
          name: this.name.trim(),
          email: this.email.trim(),
        }),
      "Profile updated.",
    );
  }

  async add(): Promise<void> {
    if (!this.selectedUser) return;

    await this.mutate(
      () => this.profileData.add(this.selectedUser),
      "Team member added.",
    );
  }

  async remove(member: User): Promise<void> {
    if (!window.confirm("Remove " + member.name + " from your team?")) return;

    await this.mutate(
      () => this.profileData.remove(member.id),
      "Team member removed.",
    );
  }
}
