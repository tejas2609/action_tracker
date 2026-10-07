# Action Tracker frontend - structured Angular 19

## Run

1. Back up your frontend.
2. Replace its entire src folder with this src folder. Remove the old loose component files.
3. Keep your backend running and its existing login/profile/dashboard endpoints.
4. Run npm ci, then npm start.
5. Run npm run build to check production compilation.

The ZIP includes the existing Angular configuration and lockfile for a complete frontend. No backend migration is added by this refactor.

## Structure

main.ts bootstraps only. app.config.ts provides initialization, HTTP and routing. app.routes.ts defines lazy routes and protected workspace navigation.

Each component has its own .component.ts, .component.html and .component.scss in one folder. No spec.ts files or new UI dependencies. Component-specific CSS is scoped to its component. styles/_base.scss contains only global tokens, reset, typography, common controls and reusable utilities; styles.scss imports it.

Core services separate transport/feedback, session, auth and organization user loading. Feature services own dashboard, commitments, meetings, search and profile endpoints; the chat service is reused by the chat panel and follow-up drawer. panels.service.ts owns drawer/chat selection. Feature components retain their existing domain workflows. Simple typed response contracts remain in models.ts to avoid unnecessary files.

Login uses /login and Reactive Forms. Workspace and feature routes are lazy-loaded. Expired sessions return to login. Existing promises, meeting review, chat, search, profiles, team management, dependency graph and dashboard behavior are preserved.

A name change still changes the temporary username, as in the provided backend. Styling file separation does not itself increase the JS bundle; Angular compiles external templates and scopes component styles.

## Validation

Angular production compilation passed. All 17 component triplets have existing external HTML and SCSS files; there are no inline templates, literal inline styles, or spec files. Application dependencies are unchanged.

Initial build payload: approximately 293 KB raw (85 KB estimated transfer), compared with 367 KB raw (102 KB estimated transfer) for the uploaded source, under equivalent optimized compilation. Initial payload is not the sum of all lazy feature chunks.

Browser interaction testing was unavailable because the browser executable could not be downloaded in this environment. Test against your running backend after replacement, particularly login/logout, /profile direct navigation, team changes, meeting review, dashboard pagination, drawer editing, and chat.

## Source directory

```text
src/app/app.component.html
src/app/app.component.scss
src/app/app.component.ts
src/app/app.config.ts
src/app/app.routes.ts
src/app/core/api.service.ts
src/app/core/auth.guard.ts
src/app/core/auth.interceptor.ts
src/app/core/auth.service.ts
src/app/core/models.ts
src/app/core/panels.service.ts
src/app/core/session.service.ts
src/app/core/users.service.ts
src/app/features/auth/login/login.component.html
src/app/features/auth/login/login.component.scss
src/app/features/auth/login/login.component.ts
src/app/features/commitments/commitments.component.html
src/app/features/commitments/commitments.component.scss
src/app/features/commitments/commitments.component.ts
src/app/features/commitments/commitments.service.ts
src/app/features/dashboard/dashboard.component.html
src/app/features/dashboard/dashboard.component.scss
src/app/features/dashboard/dashboard.component.ts
src/app/features/dashboard/dashboard.service.ts
src/app/features/detail/detail.component.html
src/app/features/detail/detail.component.scss
src/app/features/detail/detail.component.ts
src/app/features/meetings/meetings.component.html
src/app/features/meetings/meetings.component.scss
src/app/features/meetings/meetings.component.ts
src/app/features/meetings/meetings.service.ts
src/app/features/profile/profile.component.html
src/app/features/profile/profile.component.scss
src/app/features/profile/profile.component.ts
src/app/features/profile/profile.service.ts
src/app/features/search/search.component.html
src/app/features/search/search.component.scss
src/app/features/search/search.component.ts
src/app/features/search/search.service.ts
src/app/features/users/users.component.html
src/app/features/users/users.component.scss
src/app/features/users/users.component.ts
src/app/layout/header/header.component.html
src/app/layout/header/header.component.scss
src/app/layout/header/header.component.ts
src/app/layout/navigation.ts
src/app/layout/sidebar/sidebar.component.html
src/app/layout/sidebar/sidebar.component.scss
src/app/layout/sidebar/sidebar.component.ts
src/app/layout/workspace-shell/workspace-shell.component.html
src/app/layout/workspace-shell/workspace-shell.component.scss
src/app/layout/workspace-shell/workspace-shell.component.ts
src/app/shared/chat-panel/chat-panel.component.html
src/app/shared/chat-panel/chat-panel.component.scss
src/app/shared/chat-panel/chat-panel.component.ts
src/app/shared/chat-panel/chat.service.ts
src/app/shared/commitment-drawer/commitment-drawer.component.html
src/app/shared/commitment-drawer/commitment-drawer.component.scss
src/app/shared/commitment-drawer/commitment-drawer.component.ts
src/app/shared/commitment-list/commitment-list.component.html
src/app/shared/commitment-list/commitment-list.component.scss
src/app/shared/commitment-list/commitment-list.component.ts
src/app/shared/dependency-graph/dependency-graph.component.html
src/app/shared/dependency-graph/dependency-graph.component.scss
src/app/shared/dependency-graph/dependency-graph.component.ts
src/app/shared/pagination/pagination.component.html
src/app/shared/pagination/pagination.component.scss
src/app/shared/pagination/pagination.component.ts
src/index.html
src/main.ts
src/styles/_base.scss
src/styles.scss
```
