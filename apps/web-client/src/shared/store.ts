import { create } from "zustand";

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
}));
