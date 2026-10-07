import {
  Component,
  input,
  output,
  ChangeDetectionStrategy,
} from "@angular/core";
@Component({
  selector: "page-controls",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./pagination.component.html",
  styleUrl: "./pagination.component.scss",
})
export class Pagination {
  total = input(0);
  page = input(1);
  size = input(10);
  change = output<number>();
  pages() {
    return Math.max(1, Math.ceil(this.total() / this.size()));
  }
  end() {
    return Math.min(this.total(), this.page() * this.size());
  }
}
