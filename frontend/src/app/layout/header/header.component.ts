import { Component, inject, ChangeDetectionStrategy } from "@angular/core";
import { SessionService } from "../../core/session.service";
@Component({
  selector: "app-header",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./header.component.html",
  styleUrl: "./header.component.scss",
})
export class Header {
  session = inject(SessionService);
}
