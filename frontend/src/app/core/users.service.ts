import { inject, Injectable, signal } from "@angular/core";
import { Api } from "./api.service";
import { SessionService } from "./session.service";
import { User } from "./models";
@Injectable({ providedIn: "root" })
export class UsersService {
  private api = inject(Api);
  private session = inject(SessionService);
  readonly users = signal<User[]>([]);
  private pending?: Promise<User[]>;
  private generation = 0;
  clear(): void {
    this.generation++;
    this.pending = undefined;
    this.users.set([]);
  }
  loadUsers(): Promise<User[]> {
    if (this.pending) return this.pending;
    const generation = this.generation,
      userId = this.session.user()?.id;
    const request = this.api
      .call<{ items: User[] }>("GET", "/users", undefined, true)
      .then((result) => {
        if (
          generation === this.generation &&
          userId === this.session.user()?.id
        )
          this.users.set(result.items);
        return result.items;
      })
      .finally(() => {
        if (this.pending === request) this.pending = undefined;
      });
    this.pending = request;
    return request;
  }
}
