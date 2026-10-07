import { Component, inject, OnInit } from "@angular/core";
import { ActivatedRoute, Router } from "@angular/router";
import { Panels } from "../../core/panels.service";
@Component({
  standalone: true,
  templateUrl: "./detail.component.html",
  styleUrl: "./detail.component.scss",
})
export class Detail implements OnInit {
  route = inject(ActivatedRoute);
  router = inject(Router);
  panels = inject(Panels);
  ngOnInit() {
    const id = this.route.snapshot.paramMap.get("id");
    if (id) {
      void this.router
        .navigateByUrl("/commitments")
        .then(() => this.panels.open(id));
    }
  }
}
