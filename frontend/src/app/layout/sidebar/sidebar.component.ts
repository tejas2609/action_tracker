import { Component, inject, ChangeDetectionStrategy } from "@angular/core";
import { Router, RouterLink, RouterLinkActive } from "@angular/router";
import { SessionService } from "../../core/session.service";
import { AuthService } from "../../core/auth.service";
import { Panels } from "../../core/panels.service";
import { NAVIGATION } from "../navigation";
import { MatIconModule } from '@angular/material/icon';
@Component({
  selector: "app-sidebar",
  standalone: true,
  imports: [RouterLink, RouterLinkActive, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./sidebar.component.html",
  styleUrl: "./sidebar.component.scss",
})
export class Sidebar {
  session = inject(SessionService);
  nav = NAVIGATION;
  private auth = inject(AuthService);
  private panels = inject(Panels);
  private router = inject(Router);
  async logout(): Promise<void> {
    this.panels.close();
    this.panels.closeChat();
    try {
      await this.auth.logout();
    } catch {
      /* local session is cleared even if server is unavailable */
    } finally {
      await this.router.navigateByUrl("/login");
    }
  }
}
