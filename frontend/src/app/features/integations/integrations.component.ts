import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from "@angular/core";

import { ActivatedRoute, Router } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";

import {
  GmailStatus,
  IntegrationsService,
} from "./integrations.service";

@Component({
  standalone: true,
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./integrations.component.html",
  styleUrl: "./integrations.component.scss",
})
export class Integrations implements OnInit {
  private integrations = inject(IntegrationsService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  readonly data = signal<GmailStatus | null>(null);
  readonly working = signal(false);
  readonly message = signal("");
  readonly failed = signal(false);

  async ngOnInit(): Promise<void> {
    const result = this.route.snapshot.queryParamMap.get("gmail");

    const messages: Record<string, string> = {
      connected: "Gmail connected successfully.",

      cancelled: "Google authorization was cancelled.",

      permissions_missing:
        "Grant profile, email, and Gmail read permissions to connect.",

      reconnect_required:
        "Google did not provide offline access. Please connect again.",

      mailbox_unavailable:
        "Gmail is unavailable for this account. Check the Gmail API " +
        "setup or choose another account.",

      failed:
        "Gmail could not connect. Check your setup and try again.",
    };

    if (result) {
      this.message.set(messages[result] ?? messages["failed"]);
      this.failed.set(result !== "connected");

      await this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { gmail: null },
        queryParamsHandling: "merge",
        replaceUrl: true,
      });
    }

    await this.load();
  }

  async load(): Promise<void> {
    this.working.set(true);

    try {
      this.data.set(await this.integrations.status());
    } catch {
      // The shared API service displays the error.
    } finally {
      this.working.set(false);
    }
  }

  async connect(): Promise<void> {
    if (this.working()) return;

    this.working.set(true);
    this.message.set("");

    try {
      const result = await this.integrations.connect();
      const url = new URL(result.authorization_url);

      if (url.origin !== "https://accounts.google.com") {
        throw new Error("Invalid authorization URL");
      }

      window.location.assign(url.href);
    } catch {
      this.failed.set(true);
      this.message.set("Unable to start the Gmail connection.");
      this.working.set(false);
    }
  }

  async disconnect(): Promise<void> {
    if (this.working()) return;

    const confirmed = window.confirm(
      "Disconnect Gmail and revoke this application's Google access?",
    );

    if (!confirmed) return;

    this.working.set(true);
    this.message.set("");

    try {
      this.data.set(await this.integrations.disconnect());
      this.failed.set(false);
      this.message.set("Gmail disconnected.");
    } catch {
      // The shared API service displays the error.
    } finally {
      this.working.set(false);
    }
  }
}