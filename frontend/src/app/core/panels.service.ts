import { Injectable, signal } from "@angular/core";
import { User } from "./models";
@Injectable({ providedIn: "root" })
export class Panels {
  commitment = signal<string | null>(null);
  peer = signal<User | null>(null);
  open(id: string) {
    this.commitment.set(id);
  }
  close() {
    this.commitment.set(null);
  }
  chat(user: User) {
    this.peer.set(user);
  }
  closeChat() {
    this.peer.set(null);
  }
}
