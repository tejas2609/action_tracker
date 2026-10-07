import { Injectable, signal } from "@angular/core";
import { User } from "./models";
@Injectable({ providedIn: "root" })
export class SessionService {
  readonly user = signal<User | null>(null);
  readonly ready = signal(false);
  get token(): string | null {
    return sessionStorage.getItem("tracker-token");
  }
  set(token: string, user: User): void {
    sessionStorage.setItem("tracker-token", token);
    this.user.set(user);
  }
  clear(): void {
    sessionStorage.removeItem("tracker-token");
    this.user.set(null);
  }
}
