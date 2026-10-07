import { inject, Injectable } from "@angular/core";
import { Api } from "./api.service";
import { SessionService } from "./session.service";
import { UsersService } from "./users.service";
import { User } from "./models";
@Injectable({ providedIn: "root" })
export class AuthService {
  private api = inject(Api);
  private session = inject(SessionService);
  private users = inject(UsersService);
  private initialization?: Promise<void>;
  initialize(): Promise<void> {
    return (this.initialization ??= this.restore());
  }
  private async restore(): Promise<void> {
    try {
      if (this.session.token)
        this.session.user.set(
          await this.api.call<User>("GET", "/auth/me", undefined, true),
        );
    } catch {
      this.session.clear();
    } finally {
      this.session.ready.set(true);
    }
  }
  async login(username: string, password: string): Promise<void> {
    const result = await this.api.call<{ token: string; user: User }>(
      "POST",
      "/auth/login",
      { username: username.trim().toLowerCase(), password },
    );
    this.users.clear();
    this.session.set(result.token, result.user);
    this.api.changed();
  }
  async logout(): Promise<void> {
    try {
      await this.api.call("POST", "/auth/logout");
    } finally {
      this.session.clear();
      this.users.clear();
      this.api.changed();
    }
  }
}
