//! Structured logging, matching `nova-observability`'s wire shape exactly.
//!
//! Five fields — `timestamp`, `level`, `logger`, `message`, `service` — as JSON
//! lines on stdout, so the companion's logs aggregate alongside every engine's
//! without a second parser. Written by hand rather than configured from a
//! logging crate: matching an existing five-field shape is less code than
//! bending a framework into it, and TDD 4F.3 §16 asks for the smallest
//! reasonable dependency set.
//!
//! **Paths are not logged.** `log_observation` records the *file name* and the
//! outcome, never the directory chain. The path is not secret from the engine —
//! **D-4F3-2** sends it there deliberately — but a log line is a different
//! audience with a different lifetime, and TDD 4F.3 §9 requires logs not to
//! expose it unnecessarily. The one exception is a startup configuration error
//! naming the operator's own misconfigured value, which they must see to fix.

use std::path::Path;

use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

const SERVICE: &str = "nova-companion";

pub fn log(level: &str, logger: &str, message: &str, extra: serde_json::Value) {
    let timestamp = OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .unwrap_or_else(|_| String::from("unavailable"));

    let mut record = serde_json::json!({
        "timestamp": timestamp,
        "level": level,
        "logger": logger,
        "message": message,
        "service": SERVICE,
    });

    if let (Some(object), Some(fields)) = (record.as_object_mut(), extra.as_object()) {
        for (key, value) in fields {
            object.insert(key.clone(), value.clone());
        }
    }

    println!("{record}");
}

pub fn info(logger: &str, message: &str, extra: serde_json::Value) {
    log("INFO", logger, message, extra);
}

pub fn warning(logger: &str, message: &str, extra: serde_json::Value) {
    log("WARNING", logger, message, extra);
}

pub fn error(logger: &str, message: &str, extra: serde_json::Value) {
    log("ERROR", logger, message, extra);
}

/// The file's final segment, for logs.
///
/// One segment carries enough to debug with and no directory structure. The
/// same reduction `perception-engine` applies when it builds `label`, for the
/// same reason.
pub fn loggable_name(path: &Path) -> String {
    path.file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_else(|| String::from("<unnamed>"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn a_loggable_name_is_one_segment_and_carries_no_directories() {
        // TDD 4F.3 §9: logs must not expose the raw path unnecessarily.
        let name = loggable_name(&PathBuf::from("/home/ada/projects/secret-client/notes.md"));
        assert_eq!(name, "notes.md");
        assert!(!name.contains('/'));
        assert!(!name.contains("ada"));
        assert!(!name.contains("secret-client"));
    }

    #[test]
    fn a_pathological_path_still_yields_something_loggable() {
        assert_eq!(loggable_name(&PathBuf::from("/")), "<unnamed>");
    }
}
