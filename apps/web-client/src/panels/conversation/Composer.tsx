import { zodResolver } from "@hookform/resolvers/zod";
import { Button, TextField } from "@nova/ui";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useUiStore } from "../../shared/store";

/**
 * Where a turn is typed.
 *
 * Draft text is the one thing this panel keeps locally (doc 04 §5's
 * "ephemeral UI state" row, and TDD 4A §5.2 property 2's explicit
 * exemption). The sent turn is **not** rendered here -- it appears in the
 * transcript when `communication.turn.received` comes back over the socket,
 * which is the system confirming it rather than this client assuming it.
 */

const composerSchema = z.object({
  content: z.string().trim().min(1),
});

type ComposerForm = z.infer<typeof composerSchema>;

export type ComposerProps = {
  sessionId: string;
  disabled?: boolean;
  busy?: boolean;
  onSend: (content: string) => void;
};

export function Composer({ sessionId, disabled = false, busy = false, onSend }: ComposerProps) {
  const draft = useUiStore((state) => state.drafts[sessionId] ?? "");
  const setDraft = useUiStore((state) => state.setDraft);
  const clearDraft = useUiStore((state) => state.clearDraft);

  const { register, handleSubmit, reset } = useForm<ComposerForm>({
    resolver: zodResolver(composerSchema),
    values: { content: draft },
  });

  return (
    <form
      className="mt-3 flex items-end gap-2"
      onSubmit={handleSubmit((values) => {
        onSend(values.content.trim());
        clearDraft(sessionId);
        reset({ content: "" });
      })}
    >
      <TextField
        label="Message"
        hideLabel
        className="flex-1"
        placeholder="Say something to NOVA"
        autoComplete="off"
        disabled={disabled}
        {...register("content", {
          onChange: (event) => setDraft(sessionId, event.target.value),
        })}
      />
      <Button type="submit" busy={busy} disabled={disabled}>
        Send
      </Button>
    </form>
  );
}
