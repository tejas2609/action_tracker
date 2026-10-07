import {
  Component,
  inject,
  effect,
  ChangeDetectionStrategy,
} from "@angular/core";
import { Router, RouterOutlet } from "@angular/router";
import { Api } from "../../core/api.service";
import { SessionService } from "../../core/session.service";
import { UsersService } from "../../core/users.service";
import { Panels } from "../../core/panels.service";
import { Sidebar } from "../sidebar/sidebar.component";
import { Header } from "../header/header.component";
import { CommitmentDrawer } from "../../shared/commitment-drawer/commitment-drawer.component";
import { ChatPanel } from "../../shared/chat-panel/chat-panel.component";
@Component({
  selector: "app-workspace-shell",
  standalone: true,
  imports: [RouterOutlet, Sidebar, Header, CommitmentDrawer, ChatPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./workspace-shell.component.html",
  styleUrl: "./workspace-shell.component.scss",
})
export class WorkspaceShell {
  api = inject(Api);
  private session = inject(SessionService);
  private router = inject(Router);
  private panels = inject(Panels);
  private users = inject(UsersService);
  constructor() {
    effect(() => {
      if (!this.session.user()) {
        this.panels.close();
        this.panels.closeChat();
        this.users.clear();
        void this.router.navigateByUrl("/login");
      }
    });
    void this.users
      .loadUsers()
      .catch(() => this.api.error.set("Could not load the user directory."));
  }
}
