import { Routes } from "@angular/router";
import { authGuard, guestGuard } from "./core/auth.guard";
export const routes: Routes = [
  {
    path: "login",
    canActivate: [guestGuard],
    loadComponent: () =>
      import("./features/auth/login/login.component").then((m) => m.Login),
  },
  {
    path: "",
    canActivate: [authGuard],
    canActivateChild: [authGuard],
    loadComponent: () =>
      import("./layout/workspace-shell/workspace-shell.component").then(
        (m) => m.WorkspaceShell,
      ),
    children: [
      {
        path: "",
        pathMatch: "full",
        loadComponent: () =>
          import("./features/dashboard/dashboard.component").then(
            (m) => m.Dashboard,
          ),
      },
      {
        path: "meetings",
        loadComponent: () =>
          import("./features/meetings/meetings.component").then(
            (m) => m.Meetings,
          ),
      },
      {
        path: "commitments",
        loadComponent: () =>
          import("./features/commitments/commitments.component").then(
            (m) => m.Commitments,
          ),
      },
      {
        path: "commitments/:id",
        loadComponent: () =>
          import("./features/detail/detail.component").then((m) => m.Detail),
      },
      {
        path: "users",
        loadComponent: () =>
          import("./features/users/users.component").then((m) => m.Users),
      },
      {
        path: "search",
        loadComponent: () =>
          import("./features/search/search.component").then((m) => m.Search),
      },
      {
        path: "profile",
        loadComponent: () =>
          import("./features/profile/profile.component").then((m) => m.Profile),
      },
      {
        path: "integrations",
        loadComponent: () =>
          import("./features/integations/integrations.component").then(
            (m) => m.Integrations,
          ),
      },
      {
        path: "chat",
        loadComponent: () =>
          import("./features/chat/chat.component").then((m) => m.Chat),
      },
    ],
  },
  { path: "**", redirectTo: "" },
];
