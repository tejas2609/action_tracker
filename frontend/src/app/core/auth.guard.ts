import { inject } from "@angular/core";
import { CanActivateFn, Router } from "@angular/router";
import { AuthService } from "./auth.service";
import { SessionService } from "./session.service";
export const authGuard: CanActivateFn = async (_, state) => {
  const auth = inject(AuthService),
    session = inject(SessionService),
    router = inject(Router);
  await auth.initialize();
  return session.user()
    ? true
    : router.createUrlTree(["/login"], {
        queryParams: { returnUrl: state.url },
      });
};
export const guestGuard: CanActivateFn = async () => {
  const auth = inject(AuthService),
    session = inject(SessionService),
    router = inject(Router);
  await auth.initialize();
  return session.user() ? router.createUrlTree(["/"]) : true;
};
