import { CommitmentsService } from "../../features/commitments/commitments.service";
import { SessionService } from "../../core/session.service";
import {
  Component,
  input,
  inject,
  ChangeDetectionStrategy,
} from "@angular/core";
import { DatePipe } from "@angular/common";
import { Commitment } from "../../core/models";
import { Api } from "../../core/api.service";
import { Panels } from "../../core/panels.service";
@Component({
  selector: "commitment-list",
  standalone: true,
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./commitment-list.component.html",
  styleUrl: "./commitment-list.component.scss",
})
export class CommitmentList {
  commitmentData = inject(CommitmentsService);

  session = inject(SessionService);
  items = input<Commitment[]>([]);
  api = inject(Api);
  panels = inject(Panels);
  editable(c: Commitment) {
    return (
      c.owner_id === this.session.user()?.id ||
      this.session.user()?.role === "Product Manager"
    );
  }
  async status(c: Commitment, event: Event) {
    const select = event.target as HTMLSelectElement;
    try {
      await this.commitmentData.update(c.id, { status: select.value });
      this.api.changed();
    } catch {
      select.value = c.status;
    }
  }
}
