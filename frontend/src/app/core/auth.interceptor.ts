import { inject } from "@angular/core";
import { HttpInterceptorFn, HttpErrorResponse } from "@angular/common/http";
import { catchError, throwError } from "rxjs";
import { SessionService } from "./session.service";
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const session = inject(SessionService);
  if (!request.url.startsWith("/api")) return next(request);
  const token = session.token;
  const authenticated = token
    ? request.clone({ setHeaders: { Authorization: "Bearer " + token } })
    : request;
  return next(authenticated).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && token && session.token === token)
        session.clear();
      return throwError(() => error);
    }),
  );
};
