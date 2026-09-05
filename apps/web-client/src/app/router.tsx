import {
  Outlet,
  RouterProvider,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";

import { AppShell } from "./AppShell";
import { SessionGate } from "./SessionGate";

/**
 * Routing, per Fork E4's stack decision (TanStack Router).
 *
 * Code-based routes rather than the file-based generator: the generator adds
 * a build step and a generated file to review, and 4A has one route. When
 * 4B adds a panel per route the trade changes; it does not yet.
 *
 * The session gate sits *above* the router outlet rather than in a
 * `beforeLoad` redirect. A redirect would flash the shell before bouncing,
 * and "is this session valid" is answered by a request that may still be in
 * flight when the route resolves.
 */

const rootRoute = createRootRoute({
  component: () => (
    <SessionGate>
      <Outlet />
    </SessionGate>
  ),
});

const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: AppShell,
});

const routeTree = rootRoute.addChildren([workspaceRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function AppRouter() {
  return <RouterProvider router={router} />;
}
