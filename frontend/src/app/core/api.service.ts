import { inject, Injectable, signal, computed } from "@angular/core";
import { HttpClient, HttpErrorResponse } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
@Injectable({ providedIn: "root" })
export class Api {
  private http = inject(HttpClient);
  private pending = signal(0);
  readonly error = signal("");
  readonly busy = computed(() => this.pending() > 0);
  readonly revision = signal(0);
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
    try {
      return await firstValueFrom(
        this.http.request<T>(method, "/api" + path, { body }),
      );
    } catch (error) {
      const response = error as HttpErrorResponse;
      const message =
        typeof response.error?.detail === "string"
          ? response.error.detail
          : response.status === 0
            ? "Cannot reach the backend. Check that it is running."
            : "Request failed. Check your input and retry.";
      if (!quiet) this.error.set(message);
      throw error;
    } finally {
      if (!quiet) this.pending.update((n) => n - 1);
    }
  }
  changed(): void {
    this.revision.update((n) => n + 1);
  }
}
