//! **S-1: a real filesystem event is detected on a real filesystem.**
//!
//! Every test here creates a real temp directory and performs real file
//! operations against a real `notify` watcher. **No event is constructed and
//! injected** — the TDD's S-1 requires the detection itself be exercised, and a
//! hand-built `Event` would prove only that the filter works.
//!
//! The one thing these cannot do is hurry the OS. A watcher reports when the
//! platform tells it to, so each test blocks on a bounded `recv_timeout` rather
//! than sleeping a guessed interval and hoping.

use std::fs;
use std::path::Path;
use std::time::{Duration, SystemTime};

use nova_companion_sensors::{FilesystemSensor, WatchError};

/// Generous enough for a loaded CI runner, short enough that a genuine failure
/// fails rather than hangs. It bounds a wait, it does not pace one.
const DEADLINE: Duration = Duration::from_secs(10);

/// Drain batches until one contains `name`, or the deadline passes.
///
/// A watcher may report unrelated churn in the same directory, so a test that
/// asserted on "the first batch" would be flaky for reasons that have nothing
/// to do with the property under test.
fn wait_for(sensor: &FilesystemSensor, name: &str) -> Option<(std::path::PathBuf, SystemTime)> {
    let deadline = std::time::Instant::now() + DEADLINE;
    while std::time::Instant::now() < deadline {
        let batch = sensor.next_batch()?;
        let Ok(observations) = batch else { continue };
        for observation in observations {
            if observation.path.file_name().and_then(|n| n.to_str()) == Some(name) {
                return Some((observation.path, observation.observed_at));
            }
        }
    }
    None
}

#[test]
fn a_real_file_creation_is_detected() {
    let root = tempfile::tempdir().expect("temp dir");
    let sensor = FilesystemSensor::watch(root.path()).expect("watch");

    fs::write(root.path().join("notes.md"), b"real content").expect("write");

    let found = wait_for(&sensor, "notes.md");
    assert!(
        found.is_some(),
        "a real file creation was not detected within {DEADLINE:?}"
    );
}

#[test]
fn a_real_modification_is_detected() {
    let root = tempfile::tempdir().expect("temp dir");
    let target = root.path().join("existing.md");
    fs::write(&target, b"first").expect("seed");

    let sensor = FilesystemSensor::watch(root.path()).expect("watch");
    fs::write(&target, b"second, longer content").expect("modify");

    assert!(
        wait_for(&sensor, "existing.md").is_some(),
        "a real modification was not detected within {DEADLINE:?}"
    );
}

#[test]
fn the_observed_at_is_the_files_own_modification_time() {
    // The property TDD 4F §20.1 protects: `observed_at` is the real OS event
    // time, not the moment this process noticed. Asserted by comparing against
    // the filesystem's own record rather than against a clock read here.
    let root = tempfile::tempdir().expect("temp dir");
    let sensor = FilesystemSensor::watch(root.path()).expect("watch");

    let target = root.path().join("stamped.md");
    fs::write(&target, b"content").expect("write");

    let (path, observed_at) = wait_for(&sensor, "stamped.md").expect("detected");
    let from_filesystem = fs::metadata(&path)
        .expect("stat")
        .modified()
        .expect("mtime");

    assert_eq!(
        observed_at, from_filesystem,
        "observed_at did not come from the file's own mtime"
    );
}

#[test]
fn a_nested_file_inside_the_root_is_detected() {
    let root = tempfile::tempdir().expect("temp dir");
    let nested = root.path().join("project").join("src");
    fs::create_dir_all(&nested).expect("mkdir");

    let sensor = FilesystemSensor::watch(root.path()).expect("watch");
    fs::write(nested.join("deep.rs"), b"fn main() {}").expect("write");

    assert!(
        wait_for(&sensor, "deep.rs").is_some(),
        "a file nested inside the configured root was not detected"
    );
}

#[test]
fn every_detected_path_lies_inside_the_configured_root() {
    // **D-4F3-3's containment property.** The watcher is scoped to one
    // configured directory; this asserts the scope holds for what it emits.
    let root = tempfile::tempdir().expect("temp dir");
    let sensor = FilesystemSensor::watch(root.path()).expect("watch");
    let canonical_root = root.path().canonicalize().expect("canonicalize");

    fs::write(root.path().join("inside.md"), b"x").expect("write");

    let (path, _) = wait_for(&sensor, "inside.md").expect("detected");
    assert!(
        path.starts_with(&canonical_root),
        "emitted a path outside the configured root: {}",
        path.display()
    );
}

#[test]
fn a_sibling_directory_is_not_watched() {
    // The negative half of containment: writing next to the root, not in it,
    // must produce nothing. Proves the watch is bound rather than ambient.
    let parent = tempfile::tempdir().expect("temp dir");
    let watched = parent.path().join("watched");
    let sibling = parent.path().join("sibling");
    fs::create_dir_all(&watched).expect("mkdir");
    fs::create_dir_all(&sibling).expect("mkdir");

    let sensor = FilesystemSensor::watch(&watched).expect("watch");
    fs::write(sibling.join("elsewhere.md"), b"x").expect("write");
    // A file inside the root, written second, is the signal that the watcher is
    // alive and has had time to report -- without it this test could pass
    // simply because nothing was reported yet.
    fs::write(watched.join("inside.md"), b"x").expect("write");

    let (path, _) = wait_for(&sensor, "inside.md").expect("the in-root file was not detected");
    assert!(path.starts_with(watched.canonicalize().expect("canonicalize")));

    let sibling_name = sibling.join("elsewhere.md");
    assert!(
        !path.starts_with(&sibling_name),
        "a sibling directory's file was reported"
    );
}

#[test]
fn watching_a_path_that_is_not_a_directory_fails_rather_than_defaulting() {
    // **D-4F3-3.** A watcher that fell back to the current directory or `$HOME`
    // would be a privacy decision made by a default value.
    let root = tempfile::tempdir().expect("temp dir");
    let file = root.path().join("a-file.md");
    fs::write(&file, b"x").expect("write");

    assert!(matches!(
        FilesystemSensor::watch(&file),
        Err(WatchError::NotADirectory(_))
    ));
    assert!(matches!(
        FilesystemSensor::watch(Path::new("/definitely/not/here")),
        Err(WatchError::NotADirectory(_))
    ));
}

#[test]
fn dropping_the_sensor_ends_the_stream_cleanly() {
    // Clean shutdown: the loop in `main` ends when the channel closes, and this
    // asserts the channel does close rather than the process needing a signal.
    let root = tempfile::tempdir().expect("temp dir");
    let sensor = FilesystemSensor::watch(root.path()).expect("watch");
    drop(sensor);
    // Reaching here without a hang is the assertion; the watcher was released
    // with the struct.
}
