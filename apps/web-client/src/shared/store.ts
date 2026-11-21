import { create } from "zustand";

import { EMPTY_EVENT_FILTERS, type EventFilters } from "../entities/events";

/**
 * Ephemeral UI state, per doc 04 §5's table.
 *
 * The boundary this file defends: **nothing here is shared cognitive state.**
 * Server state lives in TanStack Query, hydrated by `realtime/`. What is
 * allowed here is what would be lost on reload without anyone minding -- an
 * unsent draft, which panel has focus.
 *
 * TDD 4A §5.2 property 2 forbids optimistic rendering of anything affecting
 * shared cognitive state, and explicitly exempts local composer text. That
 * exemption is exactly the size of this store.
 */

type UiState = {
  /** Unsent composer text, per session. Never a sent turn. */
  drafts: Record<string, string>;
  setDraft: (sessionId: string, text: string) => void;
  clearDraft: (sessionId: string) => void;
  /**
   * Which conversation the workspace has open.
   *
   * Moved here in 4B when the panels became routes: the shell and the
   * Conversation panel are no longer parent and child, so a `useState` in
   * one could not reach the other without threading it through the router.
   *
   * It belongs here by this file's own rule -- losing it on reload costs
   * nothing, because 4A already has no transcript hydration and a reload
   * starts empty regardless. The *transcript* stays in Query where it
   * belongs; this is only the pointer to it.
   */
  activeSessionId: string | null;
  setActiveSessionId: (sessionId: string | null) => void;
  /**
   * The Events panel's filters — doc 04 §5's table puts "local filters" in
   * this store by name, and they qualify by this file's own rule: losing
   * them on reload costs nothing, and they change nothing anyone else can
   * see. The frames themselves stay in Query, unfiltered; this is only the
   * lens the operator is currently looking through.
   */
  eventFilters: EventFilters;
  setEventFilter: (dimension: keyof EventFilters, value: string) => void;
  clearEventFilters: () => void;
};

export const useUiStore = create<UiState>((set) => ({
  drafts: {},
  setDraft: (sessionId, text) =>
    set((state) => ({ drafts: { ...state.drafts, [sessionId]: text } })),
  clearDraft: (sessionId) =>
    set((state) => {
      const { [sessionId]: _removed, ...rest } = state.drafts;
      return { drafts: rest };
    }),
  activeSessionId: null,
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  eventFilters: EMPTY_EVENT_FILTERS,
  setEventFilter: (dimension, value) =>
    set((state) => ({ eventFilters: { ...state.eventFilters, [dimension]: value } })),
  clearEventFilters: () => set({ eventFilters: EMPTY_EVENT_FILTERS }),
}));
