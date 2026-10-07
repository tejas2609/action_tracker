import { SessionService } from "../../core/session.service";
import { UsersService } from "../../core/users.service";
import {
  Component,
  inject,
  signal,
  computed,
  OnInit,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Api } from "../../core/api.service";
import { Panels } from "../../core/panels.service";
@Component({
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./users.component.html",
  styleUrl: "./users.component.scss",
})
export class Users implements OnInit {
  session = inject(SessionService);
  directory = inject(UsersService);
  api = inject(Api);
  panels = inject(Panels);
  q = "";
  team = "";
  role = "";
  teams = computed(() =>
    [...new Set(this.directory.users().map((u) => u.team))].sort(),
  );
  roles = computed(() =>
    [...new Set(this.directory.users().map((u) => u.role))].sort(),
  );
  visible() {
    return this.directory
      .users()
      .filter(
        (u) =>
          (u.name + " " + u.email)
            .toLowerCase()
            .includes(this.q.toLowerCase()) &&
          (!this.team || u.team === this.team) &&
          (!this.role || u.role === this.role),
      );
  }
  async ngOnInit() {
    try {
      await this.directory.loadUsers();
    } catch {
      this.api.error.set("Cannot load the organization directory.");
    }
  }
}
