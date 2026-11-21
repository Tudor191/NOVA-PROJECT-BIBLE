//! **F-7: a watcher error must not put the directory chain into a log line.**
//!
//! `main.rs`'s `run` loop logs `problem.to_string()` under `watch_error`, so
//! `WatchError`'s `Display` *is* the log line. `notify::Error`'s own `Display`
//! appends `" about {paths:?}"` whenever `Error::paths` is non-empty, and the
//! Linux backend attaches the watched path to nearly every error it raises —
//! so before the fix this leaked the configured root through an error
//! formatter, the one path that never looks like it handles user data.
//!
//! These construct the error the way `notify` itself does (`add_path`) rather
//! than asserting on a string built here, so the test fails if a future
//! `notify` release changes how paths are attached.

use std::path::{Path, PathBuf};

use notify::{Error, ErrorKind};
use nova_companion_sensors::WatchError;

/// Several identifying segments, so "the chain did not leak" is a meaningful
/// assertion rather than one a short name would satisfy by accident.
const WATCHED: &str = "/home/ada/projects/analytical-engine/design";
const SEGMENTS: [&str; 4] = ["home", "ada", "projects", "analytical-engine"];

fn rendered(error: Error) -> String {
    WatchError::Notify(error).to_string()
}

#[test]
fn a_watcher_error_does_not_render_the_directory_chain() {
    let leaky = Error::new(ErrorKind::PathNotFound).add_path(PathBuf::from(WATCHED));

    // The property under test, stated against `notify`'s own output: its
    // `Display` really does contain the chain, and ours really does not.
    assert!(
        leaky.to_string().contains("analytical-engine"),
        "notify no longer embeds paths in Display; this guard needs revisiting"
    );

    let line = rendered(leaky);
    assert!(!line.contains(WATCHED), "the full path leaked: {line}");
    for segment in SEGMENTS {
        assert!(
            !line.contains(segment),
            "path segment {segment:?} leaked into the log line: {line}"
        );
    }
}

#[test]
fn the_error_kind_survives_redaction() {
    // Sanitizing must not cost the operator the reason. Each kind keeps its
    // own message -- that is the half with the diagnostic value in it.
    assert!(rendered(Error::new(ErrorKind::MaxFilesWatch)).contains("file watch limit"));
    assert!(rendered(Error::new(ErrorKind::WatchNotFound)).contains("watch not found"));
    assert!(rendered(Error::generic("internal channel disconnect")).contains("channel disconnect"));
    assert!(
        rendered(Error::io(std::io::Error::from(
            std::io::ErrorKind::PermissionDenied
        )))
        .contains("permission denied")
    );
}

#[test]
fn the_affected_file_name_is_still_reported() {
    // The final segment is retained deliberately: it is what the per-event logs
    // already carry (`loggable_name`), and without it an operator cannot tell
    // which file a recurring error concerns.
    let line = rendered(Error::new(ErrorKind::PathNotFound).add_path(PathBuf::from(WATCHED)));
    assert!(line.contains("design"), "no affected name reported: {line}");
}

#[test]
fn several_affected_paths_report_names_only() {
    let error = Error::new(ErrorKind::WatchNotFound)
        .add_path(PathBuf::from("/home/ada/projects/one/notes.md"))
        .add_path(PathBuf::from("/home/ada/projects/two/draft.md"));

    let line = rendered(error);
    assert!(line.contains("notes.md") && line.contains("draft.md"));
    for segment in ["home", "ada", "projects", "one", "two"] {
        assert!(
            !line.contains(segment),
            "segment {segment:?} leaked: {line}"
        );
    }
}

#[test]
fn an_error_with_no_paths_renders_cleanly() {
    // No dangling "(affecting )" when there is nothing to report.
    let line = rendered(Error::new(ErrorKind::MaxFilesWatch));
    assert!(
        !line.contains("affecting"),
        "empty path list rendered: {line}"
    );
}

#[test]
fn the_configuration_error_still_names_the_operators_own_value() {
    // The deliberate exception, asserted so a later broad redaction does not
    // silently take it away: a misconfigured watch root is the operator's own
    // input, echoed back at startup so they can fix it.
    let line = WatchError::NotADirectory(Path::new(WATCHED).to_path_buf()).to_string();
    assert!(
        line.contains(WATCHED),
        "the operator cannot see what they set: {line}"
    );
}
