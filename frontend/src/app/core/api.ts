import { inject, Injectable, signal, computed } from "@angular/core";
import {
  HttpClient,
  HttpErrorResponse,
  HttpHeaders,
} from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import { Commitment, Meeting, User, Page } from "./models";
@Injectable({ providedIn: "root" })
export class Api {
  private http = inject(HttpClient);
  private pending = signal(0);
  error = signal("");
  busy = computed(() => this.pending() > 0);
  user = signal<User | null>(null);
  ready = signal(false);
  revision = signal(0);
  users = signal<User[]>([]);
  async call<T>(
    method: string,
    path: string,
    body?: unknown,
    quiet = false,
  ): Promise<T> {
    if (!quiet) {
      this.error.set("");
      this.pending.update((n) => n + 1);
    }
    const token = sessionStorage.getItem("tracker-token");
    let headers = new HttpHeaders();
    if (token) headers = headers.set("Authorization", "Bearer " + token);
    try {
      return await firstValueFrom(
        this.http.request<T>(method, "/api" + path, { body, headers }),
      );
    } catch (e) {
      const x = e as HttpErrorResponse;
      if (x.status === 401 && this.user()) {
        sessionStorage.removeItem("tracker-token");
        this.user.set(null);
      }
      const message =
        typeof x.error?.detail === "string"
          ? x.error.detail
          : x.status === 0
            ? "Cannot reach the backend. Check that it is running."
            : "Request failed. Check your input and retry.";
      if (!quiet) this.error.set(message);
      throw e;
    } finally {
      if (!quiet) this.pending.update((n) => n - 1);
    }
  }
  async initialize() {
    try {
      if (sessionStorage.getItem("tracker-token"))
        this.user.set(
          await this.call<User>("GET", "/auth/me", undefined, true),
        );
    } catch {
      sessionStorage.removeItem("tracker-token");
    } finally {
      this.ready.set(true);
    }
  }
  async login(username: string, password: string): Promise<void> {
    const result = await this.call<{
      token: string;
      user: User;
    }>("POST", "/auth/login", {
      username: username.trim().toLowerCase(),
      password,
    });

    sessionStorage.setItem("tracker-token", result.token);
    this.user.set(result.user);
    this.revision.update((value) => value + 1);
  }
  async logout() {
    try {
      await this.call("POST", "/auth/logout");
    } finally {
      sessionStorage.removeItem("tracker-token");
      this.user.set(null);
      this.users.set([]);
    }
  }
  async loadUsers() {
    const r = await this.call<{ items: User[] }>(
      "GET",
      "/users",
      undefined,
      true,
    );
    this.users.set(r.items);
    return r.items;
  }
  async commitments(scope = "organization") {
    let page = 1;
    const rows: Commitment[] = [];
    while (true) {
      const r = await this.call<Page<Commitment>>(
        "GET",
        `/commitments?scope=${scope}&page_size=100&page=${page}`,
        undefined,
        true,
      );
      rows.push(...r.items);
      if (rows.length >= r.total || !r.items.length) return rows;
      page++;
    }
  }
  meetings() {
    return this.call<Meeting[]>("GET", "/meetings");
  }
  changed() {
    this.revision.update((n) => n + 1);
  }
}
