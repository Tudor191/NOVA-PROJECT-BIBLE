# 05 — Desktop Application Architecture

## 1. Why Tauri, not Electron (expanded from ADR-003)

The desktop app has two responsibilities the web app does not: (a) hosting the same
Command Center UI as a native window, and (b) hosting **NOVA Companion**, the process
that gives NOVA eyes and hands on the user's actual machine (Perception Engine desktop
sensors, Action Engine desktop actuators — Parts 11 & 12). Electron only solves (a).
Tauri's Rust core is a natural home for (b) as well, so the desktop app and the OS
integration daemon share one language and one workspace instead of Electron+Node
talking to a separate native helper process over some ad hoc IPC.

| Criterion | Tauri | Electron |
|---|---|---|
| Install size | ~10–20MB (uses OS webview) | ~150–250MB (bundles Chromium+Node) |
| Memory footprint | Low (no bundled Chromium process) | High |
| OS-level sensor/actuator access | Native, in-process Rust | Requires a separate native module or helper process |
| Security sandboxing | Fine-grained capability/permission system (Tauri v2) | Coarser, historically more CVEs |
| Fit with "Living Interface" always-on background process (Part 1) | Low idle resource cost — acceptable to run continuously | Heavier idle footprint, harder to justify running 24/7 |

## 2. Process architecture

```
desktop-client/  (Tauri app)
├── src-tauri/                  # Rust host process
│   ├── src/
│   │   ├── main.rs
│   │   ├── companion_bridge.rs # Embeds/supervises nova-companion as a child process or library
│   │   ├── tray.rs             # System tray — persistent NOVA presence (Part 1)
│   │   ├── window_manager.rs   # Command Center window + future HUD overlay windows
│   │   └── ipc/                # Tauri commands exposed to the webview (thin, typed)
│   └── tauri.conf.json
└── src/                        # Same React app as apps/web-client, reused via a shared package
```

The desktop shell **imports and renders `apps/web-client`** rather than maintaining a
parallel UI — the Command Center is one React application, mounted in a browser tab in
web mode and in a Tauri webview in desktop mode. Desktop-only affordances (system tray,
global hotkey wake-word activation, native notifications, HUD overlay windows) are
injected via a small `platform` abstraction (`isTauri() ? tauriApi : webApi`) so the UI
codebase never forks.

## 3. NOVA Companion (`companion/nova-companion`)

A separate Rust binary, supervised (started/health-checked/restarted) by the Tauri
host process but architecturally independent — it is a **sensor/actuator implementation
of the Perception and Action Engine contracts**, not a special-cased subsystem:

```
companion/
├── sensors/
│   ├── window_focus.rs         # Active window, title, process
│   ├── clipboard.rs
│   ├── filesystem_watch.rs     # Part 11 "Filesystem Perception"
│   ├── process_monitor.rs      # Part 11 "System Perception": CPU/GPU/RAM/battery/temp
│   └── input_activity.rs       # Aggregated (never raw keystroke content) keyboard/mouse activity
├── actuators/
│   ├── mouse_keyboard.rs       # Part 12 desktop actions
│   ├── window_control.rs
│   ├── terminal.rs             # Spawns/controls terminal sessions (PowerShell/bash/zsh)
│   └── clipboard_write.rs
└── bridge.rs                   # Publishes normalized events to the Event Bus (Part 11's
                                 # "Event Normalization"); consumes action.execute commands
```

Every sensor implements the same `Sensor` trait (`initialize`, `start`, `pause`,
`resume`, `stop`, `health_check`, `permission_status` — Part 11 "Sensor Abstraction
Layer") and every actuator implements the same `Actuator` trait matching Part 12's
Action Object Model. This is what lets new sensors/actuators (camera, AR glasses,
future robotics per Part 11/12 "Future Evolution") be added without touching
`nova-companion`'s core.

## 4. Security boundary

- Every sensor requires an explicit, revocable OS-level permission grant, surfaced in
  the Command Center's Perception panel (Part 11 "Perception Security" /
  "Perception Privacy") — camera, microphone, filesystem, clipboard, accessibility
  (for window/input control) each gated independently.
- Companion never transmits raw sensor payloads off-device by default; it publishes
  **normalized, locally-processed events** onto the local Event Bus. Cloud sync of
  perception data is opt-in per [18](18-local-first-and-cloud-sync.md).
- All actuator actions pass through the Action Engine's permission/risk pipeline
  (Part 12) even though Companion runs locally with OS-level privileges — Companion
  never self-authorizes an action; it only executes what Action Engine has already
  validated.

## 5. Offline-first desktop behavior

The desktop app is the primary target for Part 7's "Offline Mode": with `nova-host`
and `nova-companion` both running locally, and Ollama serving local models, the full
Perception → Reasoning → Action loop functions with zero network connectivity. Cloud
model calls and cloud sync degrade gracefully (queued, retried on reconnect) rather
than blocking any local capability.

## 6. Update & distribution

- Tauri's built-in updater (signed update bundles) for the desktop shell.
- `nova-companion` versioned and updated in lockstep with the desktop shell (same
  release train) to avoid Perception/Action contract drift between the two.
- `nova-host` and the backend engines update independently via their own container
  images — the desktop app is a client of `nova-host`, not a container for it, so a
  backend upgrade never requires a desktop app store review cycle.
