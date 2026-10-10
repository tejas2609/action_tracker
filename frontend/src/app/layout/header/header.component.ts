import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from "@angular/core";
import { DatePipe } from "@angular/common";
import { Router } from "@angular/router";

import { SessionService } from "../../core/session.service";
import {
  AppNotification,
  NotificationsService,
} from "../../core/notifications.service";

import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-header",
  standalone: true,
  imports: [DatePipe, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./header.component.html",
  styleUrl: "./header.component.scss",
})
export class Header {
  session = inject(SessionService);
  notifications = inject(NotificationsService);

  private router = inject(Router);

  readonly opened = signal(false);
  readonly working = signal(false);
  readonly actionError = signal("");

  async open(item: AppNotification) {
    if (this.working()) return;

    this.working.set(true);
    this.actionError.set("");

    try {
      let navigated = false;

      if (item.kind === "chat" && item.peer_id) {
        navigated = await this.router.navigate(["/chat"], {
          queryParams: { peer: item.peer_id },
        });
      } else if (item.kind === "commitment_review") {
        navigated = await this.router.navigate(["/commitments"], {
          queryParams: { view: "review" },
        });
      } else if (item.commitment_id) {
        navigated = await this.router.navigate([
          "/commitments",
          item.commitment_id,
        ]);
      }

      if (!navigated) {
        this.actionError.set("Unable to open this notification.");
        return;
      }

      await this.notifications.markRead(item.id);
      this.opened.set(false);
    } catch {
      this.actionError.set("Unable to complete the notification action.");
    } finally {
      this.working.set(false);
    }
  }
  toggleNotifications(): void {
    this.opened.update((value) => !value);
  }
}
