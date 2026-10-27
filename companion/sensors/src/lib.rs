//! Real OS filesystem observation for `nova-companion`.
//!
//! This crate is the Rust half of the sensor split ratified as **D-4F3-1**: it
//! owns *real OS filesystem observation* and nothing else. The Python half —
//! `sensors_by_source["filesystem"]` in `perception-engine` — owns registration
//! and lifecycle, and is not modelled here. A Rust process cannot implement a
//! Python `Protocol`, and this crate does not pretend to.
//!
//! **What it deliberately does not do**, each because another layer already
//! owns it:
//!
//! - **No path hashing.** `perception-engine` is the single hashing authority
//!   (**D-4F3-2**). A second implementation here would put the handle format in
//!   two languages, where a divergence produces duplicate world objects for one
//!   file rather than a loud failure.
//! - **No HTTP.** That is the binary's job; this crate emits observations and
//!   has no opinion about where they go.
//! - **No filesystem-wide watching.** **D-4F3-3** binds the watcher to an
//!   explicitly configured directory. There is no code path here that can widen
//!   that scope, which is the property that makes deferring the consent
//!   question safe.
//!
//! **What it adds in 4F.8 (A-4F8-1 (a), TDD 4F.8 §29.1): losing the root is
//! reported, never silent.** After an OS permission on the configured root is
//! withdrawn, an existing inotify watch keeps delivering events, but every
//! `stat` inside the root fails with `EACCES` (TDD 4F.8 §28.7, F-4F8-15). Until
//! 4F.8 that failure was dropped as [`Ignored::NotARegularFile`], so the stream
//! stopped with nothing said. Now the root's access is re-checked on every
//! metadata change of the root itself (`IN_ATTRIB`: a `chmod`, `chown` or ACL
//! change) and before every observation is emitted, and a denial surfaces as
//! [`SensorEvent::AccessLost`]. What to do about it is the binary's decision.

use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{Receiver, channel};
use std::time::SystemTime;

use notify::event::{CreateKind, ModifyKind};
use notify::{Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};

/// One observed filesystem change, ready to be submitted.
///
/// `observed_at` is the **file's own modification time**, not the moment this
/// process noticed it. TDD 4F §20.1 forbids fabricating the timestamp, and
/// `notify` does not supply one, so it is read from the filesystem — the real
/// OS event time, which is what AC-7's interval must start from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FilesystemObservation {
    /// The absolute path. Carried in the clear on the internal network by
    /// **D-4F3-2**, which requires only that it never reach the *persisted*
    /// payload, the outbox row, the published event, or downstream world-model
    /// data.
    pub path: PathBuf,
    pub observed_at: SystemTime,
}

/// Why an event produced no observation. Not an error type — every variant is
/// an ordinary, expected outcome, and naming them is what keeps
/// "nothing happened" distinguishable from "something broke".
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ignored {
    /// A kind this slice does not observe. Only creates and content
    /// modifications describe an object that *exists* and can be observed;
    /// `perception.workspace.observed` is a fact about a present object.
    UninterestingKind,
    /// Outside the configured root. The watcher is not recursive beyond that
    /// root, so this is defence in depth rather than the primary control.
    OutsideConfiguredRoot,
    /// Not a regular file — a directory, or something that vanished between the
    /// event and the `stat`.
    NotARegularFile,
    /// The modification time could not be read, so there is no real timestamp
    /// to report. **The event is dropped rather than stamped with the current
    /// clock**, which would be a fabricated `observed_at`.
    NoRealTimestamp,
}

/// What the watcher hands its caller: either real changes, or the news that it
/// can no longer see the configured root.
#[derive(Debug)]
pub enum SensorEvent {
    /// Real changes inside the root, each with its real timestamp.
    Observations(Vec<FilesystemObservation>),
    /// This process has lost its OS permission on the configured root.
    AccessLost(AccessLoss),
}

/// The configured root became unreadable to this process.
#[derive(Debug)]
pub struct AccessLoss {
    /// When this process found out. This is a detection time, read from the
    /// clock because that is what it is; it does not claim to be the moment
    /// the permission changed, which the OS does not report.
    pub detected_at: SystemTime,
    /// The OS's own answer. Its `Display` is the OS message alone -- std does
    /// not attach the path -- so it can be logged.
    pub error: std::io::Error,
}

/// Can this process still use the configured root?
///
/// Both halves of "use" are checked, because withdrawing either loses the
/// directory: listing it needs **read** permission on the root, and reaching
/// anything inside it needs **search** (execute) permission, which resolving
/// `root/.` exercises. `Ok` means both still hold.
pub fn check_access(root: &Path) -> std::io::Result<()> {
    std::fs::read_dir(root)?;
    std::fs::metadata(root.join("."))?;
    Ok(())
}

/// `Some` when `root` is denied to this process: [`check_access`], reduced to
/// the one failure that is a permission revocation.
///
/// Only a **permission** failure counts. A root that vanished, or any other
/// I/O failure, is not a permission revocation and is not reported as one --
/// that would be a guess about why access failed.
pub fn access_lost(root: &Path) -> Option<AccessLoss> {
    match check_access(root) {
        Err(error) if error.kind() == ErrorKind::PermissionDenied => Some(AccessLoss {
            detected_at: SystemTime::now(),
            error,
        }),
        _ => None,
    }
}

/// An event kind that can become an observation: only creates and content
/// modifications describe an object that exists and can be observed.
fn is_observable(kind: &EventKind) -> bool {
    matches!(
        kind,
        EventKind::Create(CreateKind::File)
            | EventKind::Create(CreateKind::Any)
            | EventKind::Modify(ModifyKind::Data(_))
            | EventKind::Modify(ModifyKind::Any)
    )
}

/// An event after which the root's access must be re-checked: a metadata
/// change of the root itself, which is how a `chmod` on it arrives, or any
/// event that would otherwise become an observation.
fn concerns_access(event: &Event, root: &Path) -> bool {
    match event.kind {
        EventKind::Modify(ModifyKind::Metadata(_)) => event.paths.iter().any(|path| path == root),
        ref kind => is_observable(kind),
    }
}

/// Decide whether one `notify` event yields an observation.
///
/// Pure apart from the `stat`, and separated from the watcher so it can be
/// tested against constructed events without a real watcher, while the watcher
/// itself is tested against a real filesystem.
pub fn observation_from(event: &Event, root: &Path) -> Result<Vec<FilesystemObservation>, Ignored> {
    if !is_observable(&event.kind) {
        return Err(Ignored::UninterestingKind);
    }

    let mut observations = Vec::new();
    for path in &event.paths {
        if !path.starts_with(root) {
            continue;
        }
        let metadata = match std::fs::metadata(path) {
            Ok(metadata) if metadata.is_file() => metadata,
            _ => continue,
        };
        let Ok(observed_at) = metadata.modified() else {
            continue;
        };
        observations.push(FilesystemObservation {
            path: path.clone(),
            observed_at,
        });
    }

    if observations.is_empty() {
        Err(Ignored::NotARegularFile)
    } else {
        Ok(observations)
    }
}

/// A live watcher over **one configured directory**.
///
/// Holds the `notify` watcher alive: dropping this stops the watch, which is
/// what makes shutdown clean without a signal-handling dance.
pub struct FilesystemSensor {
    root: PathBuf,
    events: Receiver<notify::Result<Event>>,
    _watcher: RecommendedWatcher,
}

impl FilesystemSensor {
    /// Begin watching `root`, recursively **within it and nowhere else**.
    ///
    /// Fails rather than defaulting if `root` is not an existing directory.
    /// A watcher that silently fell back to the current directory, or to
    /// `$HOME`, would be a privacy decision made by a default value
    /// (**D-4F3-3**).
    pub fn watch(root: impl AsRef<Path>) -> Result<Self, WatchError> {
        let root = root.as_ref();
        if !root.is_dir() {
            return Err(WatchError::NotADirectory(root.to_path_buf()));
        }
        // Canonicalized so the `starts_with` containment check in
        // `observation_from` compares resolved paths. Without it a symlinked or
        // `..`-containing root would make that check compare unlike things.
        let root = root.canonicalize().map_err(WatchError::Io)?;

        let (sender, events) = channel();
        let mut watcher = RecommendedWatcher::new(sender, notify::Config::default())
            .map_err(WatchError::Notify)?;
        watcher
            .watch(&root, RecursiveMode::Recursive)
            .map_err(WatchError::Notify)?;

        Ok(Self {
            root,
            events,
            _watcher: watcher,
        })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Block until the next batch of observations, the loss of the root, or
    /// the end of the watch.
    ///
    /// Returns `None` when the channel closes, which is how a clean shutdown
    /// reaches the caller's loop as an ordinary end-of-stream rather than an
    /// error.
    ///
    /// **The root's access is checked before anything is emitted** for an event
    /// that concerns it. So a change inside a root this process can no longer
    /// read is reported as [`SensorEvent::AccessLost`], never dropped and never
    /// observed. While access stays lost, every such event reports it again;
    /// whether to act on the repeat is the caller's decision.
    pub fn next_event(&self) -> Option<Result<SensorEvent, WatchError>> {
        loop {
            let event = match self.events.recv() {
                Err(_) => return None,
                Ok(Err(error)) => return Some(Err(WatchError::Notify(error))),
                Ok(Ok(event)) => event,
            };
            if concerns_access(&event, &self.root)
                && let Some(loss) = access_lost(&self.root)
            {
                return Some(Ok(SensorEvent::AccessLost(loss)));
            }
            match observation_from(&event, &self.root) {
                Ok(observations) => return Some(Ok(SensorEvent::Observations(observations))),
                // An ignored event is not an event: keep waiting rather than
                // handing the caller an empty batch to filter.
                Err(_) => continue,
            }
        }
    }
}

#[derive(Debug)]
pub enum WatchError {
    NotADirectory(PathBuf),
    Notify(notify::Error),
    Io(std::io::Error),
}

/// Render a `notify::Error` **without its path list** (finding **F-7**).
///
/// `notify`'s own `Display` ends with `" about {paths:?}"` whenever
/// `Error::paths` is non-empty, and the Linux backend attaches the watched path
/// to nearly every error it raises (`Error::io(e).add_path(path)`, throughout
/// `inotify.rs`). Rendering that verbatim would put the configured directory
/// chain into a log line through the one code path that never looks like it
/// handles user data — an error formatter.
///
/// **The kind is kept in full**, because it is the operationally useful half
/// and carries no user data: `ErrorKind::Generic`'s strings are notify's own
/// fixed literals and internal channel/mutex diagnostics, and `ErrorKind::Io`
/// wraps a raw syscall error whose `Display` is the OS message alone. Only
/// `Error::paths` is reduced — to final segments, which is exactly the rule the
/// per-event logs already follow via `loggable_name`, and no more than the
/// startup log already reports about the configured root.
fn describe(error: &notify::Error) -> String {
    let kind = match &error.kind {
        notify::ErrorKind::PathNotFound => "path not found".to_owned(),
        notify::ErrorKind::WatchNotFound => "watch not found".to_owned(),
        notify::ErrorKind::MaxFilesWatch => "OS file watch limit reached".to_owned(),
        notify::ErrorKind::InvalidConfig(config) => format!("invalid configuration: {config:?}"),
        notify::ErrorKind::Generic(message) => message.clone(),
        notify::ErrorKind::Io(source) => source.to_string(),
    };

    let names: Vec<String> = error
        .paths
        .iter()
        .filter_map(|path| path.file_name())
        .map(|name| name.to_string_lossy().into_owned())
        .collect();

    if names.is_empty() {
        kind
    } else {
        format!("{kind} (affecting {})", names.join(", "))
    }
}

impl std::fmt::Display for WatchError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            // The path is named here because this is a startup configuration
            // error the operator must act on, and it is their own configured
            // value being echoed back. Deliberate, and the only such place.
            Self::NotADirectory(path) => {
                write!(
                    formatter,
                    "configured watch root is not a directory: {}",
                    path.display()
                )
            }
            Self::Notify(error) => {
                write!(formatter, "filesystem watcher failed: {}", describe(error))
            }
            // `std::io::Error`'s own `Display` is the OS message alone -- std
            // does not attach the operand path -- so the `canonicalize` failure
            // this wraps needs no equivalent treatment.
            Self::Io(error) => write!(formatter, "filesystem watcher io failed: {error}"),
        }
    }
}

impl std::error::Error for WatchError {}
