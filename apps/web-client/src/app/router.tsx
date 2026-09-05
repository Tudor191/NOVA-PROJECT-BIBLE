import {
  Outlet,
  RouterProvider,
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
} from "@tanstack/react-router";

import { AppShell } from "./AppShell";
import { SessionGate } from "./SessionGate";

/**
 * Routing, per Fork E4's stack decision (TanStack Router).
 *
 * Still code-based rather than the file-based generator. 4A predicted the
 * trade would change "when 4B adds a panel per route"; having added them,
 * it has not -- seven `createRoute` calls in one readable file cost less
 * than a build step plus a generated artefact to review, and the panels are
 * not nested.
 *
 * **Every panel below the shell is lazily loaded.** Each pulls its own
 * entity module, and the Reasoning and Planning panels pull generated
 * contract types with them; bundling all seven into the initial download
 * would make the Conversation panel -- the one AC-1 measures -- wait for
 * six panels the operator may never open.
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

/**
 * The shell is a layout route, so it does not remount between panels.
 * `RealtimeProvider` lives inside it: a remount would drop the WebSocket
 * and lose every frame during the reconnect, which is most visible in the
 * Events panel -- the one place a hole in the stream is the subject.
 */
const shellRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "shell",
  component: AppShell,
});

const conversationRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/",
  component: lazyRouteComponent(
    () => import("../panels/conversation/ConversationPanel"),
    "ConversationPanel",
  ),
});

const planningRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/planning",
  component: lazyRouteComponent(
    () => import("../panels/planning/PlanningPanel"),
    "PlanningPanel",
  ),
});

const reasoningRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/reasoning",
  component: lazyRouteComponent(
    () => import("../panels/reasoning/ReasoningTracePanel"),
    "ReasoningTracePanel",
  ),
});

const capabilitiesRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/capabilities",
  component: lazyRouteComponent(
    () => import("../panels/capabilities/CapabilitiesPanel"),
    "CapabilitiesPanel",
  ),
});

const approvalsRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/approvals",
  component: lazyRouteComponent(
    () => import("../panels/approvals/ApprovalsPanel"),
    "ApprovalsPanel",
  ),
});

const eventsRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/events",
  component: lazyRouteComponent(() => import("../panels/events/EventsPanel"), "EventsPanel"),
});

const healthRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: "/health",
  component: lazyRouteComponent(() => import("../panels/health/HealthPanel"), "HealthPanel"),
});

const routeTree = rootRoute.addChildren([
  shellRoute.addChildren([
    conversationRoute,
    planningRoute,
    reasoningRoute,
    capabilitiesRoute,
    approvalsRoute,
    eventsRoute,
    healthRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function AppRouter() {
  return <RouterProvider router={router} />;
}
