import {
  Component,
  inject,
  signal,
  ChangeDetectionStrategy,
} from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Router, ActivatedRoute } from "@angular/router";
import { Api } from "../../../core/api.service";
import { AuthService } from "../../../core/auth.service";
@Component({
  selector: "app-login",
  standalone: true,
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./login.component.html",
  styleUrl: "./login.component.scss",
})
export class Login {
  api = inject(Api);
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  signingIn = signal(false);
  form = inject(FormBuilder).nonNullable.group({
    username: ["", [Validators.required, Validators.maxLength(120)]],
    password: ["", [Validators.required, Validators.maxLength(200)]],
  });
  async login(): Promise<void> {
    if (this.form.invalid || this.signingIn()) return;
    const { username, password } = this.form.getRawValue();
    if (!username.trim()) return;
    this.signingIn.set(true);
    this.form.disable();
    try {
      await this.auth.login(username, password);
      this.form.controls.password.reset("");
      const target = this.route.snapshot.queryParamMap.get("returnUrl");
      await this.router.navigateByUrl(
        target &&
          target.startsWith("/") &&
          !target.startsWith("//") &&
          !target.startsWith("/login")
          ? target
          : "/",
      );
    } catch {
      /* Api displays the backend error. */
    } finally {
      this.signingIn.set(false);
      this.form.enable();
    }
  }
}
