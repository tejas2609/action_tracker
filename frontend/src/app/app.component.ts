import { Component, ChangeDetectionStrategy, inject } from "@angular/core";
import { RouterOutlet } from "@angular/router";
import { NotificationsService } from "./core/notifications.service";
@Component({
  selector: "app-root",
  standalone: true,
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./app.component.html",
  styleUrl: "./app.component.scss",
})
export class AppComponent {
  // Observe login and restored sessions before the workspace header is mounted.
  private readonly notifications = inject(NotificationsService);
}
