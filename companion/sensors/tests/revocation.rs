//! **D1: a withdrawn OS permission on the watched root is detected and reported,
//! never silently dropped** (TDD 4F.8 §29.1 A-4F8-1 (a); §29.5 item 1).
//!
//! Every test here changes a real directory's real mode bits and watches what a
//! real `notify` watcher then delivers. Nothing is constructed or injected.
//!
//! **These tests must run as a non-root user.** Root bypasses permission
//! checks, so a `chmod` would deny root nothing and a revocation test would
//! pass without testing anything. `revoke` therefore asserts that the OS really
//! denies access after the `chmod`, and fails loudly if it does not. CI runs
//! `cargo test` as the runner's own unprivileged user.
//!
//! **What they establish about the kernel** (F-4F8-7, F-4F8-15): an existing
//! inotify watch keeps delivering events after the root's mode changes, and the
//! `chmod` itself arrives as `IN_ATTRIB` on the root. Both are asserted rather
//! than assumed, on whichever kernel runs them.

use std::fs::{self, Permissions};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{Receiver, channel};
use std::thread;
use std::time::Duration;

use nova_companion_sensors::{FilesystemSensor, SensorEvent, check_access};

/// Bounds a wait for something that must happen. It does not pace anything.
const DEADLINE: Duration = Duration::from_secs(10);

/// How long to watch for something that must **not** happen. A negative can
/// only ever be shown over a window; this one is several times the latency any
/// real event in these tests showed.
const QUIET: Duration = Duration::from_secs(1);

/// What a test sees of the sensor's stream.
#[derive(Debug)]
enum Seen {
    Observed(Vec<PathBuf>),
    AccessLost(std::io::ErrorKind),
}

/// The sensor, moved onto its own thread so a test can wait with a timeout.
/// `next_event` blocks, and a test that needs to show *nothing* arrived cannot
/// block forever to show it.
fn stream(sensor: FilesystemSensor) -> Receiver<Seen> {
    let (sender, receiver) = channel();
    thread::spawn(move || {
        while let Some(next) = sensor.next_event() {
            let seen = match next {
                Ok(SensorEvent::Observations(observations)) => {
                    Seen::Observed(observations.into_iter().map(|o| o.path).collect())
                }
                Ok(SensorEvent::AccessLost(loss)) => Seen::AccessLost(loss.error.kind()),
                Err(_) => continue,
            };
            if sender.send(seen).is_err() {
                return;
            }
        }
    });
    receiver
}

/// Restores a usable mode when the test ends, however it ends, so the temp
/// directory can be removed.
struct Restore<'a>(&'a Path);

impl Drop for Restore<'_> {
    fn drop(&mut self) {
        let _ = fs::set_permissions(self.0, Permissions::from_mode(0o755));
    }
}

/// Withdraw permission on `root` by setting `mode`, and prove the OS now
/// denies this process.
fn revoke(root: &Path, mode: u32) {
    fs::set_permissions(root, Permissions::from_mode(mode)).expect("chmod");
    assert!(
        check_access(root).is_err(),
        "the OS still grants access after chmod {mode:o}. These tests must run as a \
         non-root user: root bypasses permission checks, so nothing here would be tested"
    );
}

fn next_within(events: &Receiver<Seen>, within: Duration) -> Option<Seen> {
    events.recv_timeout(within).ok()
}

#[test]
fn revoking_the_root_is_reported_from_the_roots_own_attrib_event() {
    let root = tempfile::tempdir().expect("temp dir");
    let _restore = Restore(root.path());
    let events = stream(FilesystemSensor::watch(root.path()).expect("watch"));

    revoke(root.path(), 0o000);

    // Nothing was written: the only event is the chmod itself, IN_ATTRIB on
    // the root. If it did not arrive, or were not checked, this would time out.
    match next_within(&events, DEADLINE) {
        Some(Seen::AccessLost(kind)) => assert_eq!(kind, std::io::ErrorKind::PermissionDenied),
        other => panic!("expected the revocation to be reported, saw {other:?}"),
    }
}

#[test]
fn a_change_after_the_revocation_is_reported_never_observed_and_never_dropped() {
    // F-4F8-15: before 4F.8, this change was dropped as `NotARegularFile` with
    // no report. Mode 0o300 keeps write and search for the owner but removes
    // read, so this process can still create a file inside the root while it
    // can no longer list the root.
    let root = tempfile::tempdir().expect("temp dir");
    let _restore = Restore(root.path());
    let events = stream(FilesystemSensor::watch(root.path()).expect("watch"));

    revoke(root.path(), 0o300);
    assert!(
        matches!(
            next_within(&events, DEADLINE),
            Some(Seen::AccessLost(std::io::ErrorKind::PermissionDenied))
        ),
        "the chmod itself was not reported"
    );
    assert!(
        next_within(&events, QUIET).is_none(),
        "something arrived with nothing written"
    );

    fs::write(
        root.path().join("after.md"),
        b"written after the revocation",
    )
    .expect("write");

    // The existing watch still delivers (F-4F8-7), and what it delivers is
    // reported as the loss, not observed and not dropped.
    let mut reported = false;
    while let Some(seen) = next_within(&events, if reported { QUIET } else { DEADLINE }) {
        match seen {
            Seen::AccessLost(kind) => {
                assert_eq!(kind, std::io::ErrorKind::PermissionDenied);
                reported = true;
            }
            Seen::Observed(paths) => {
                panic!("a change inside a revoked root was observed: {paths:?}")
            }
        }
    }
    assert!(
        reported,
        "a change after the revocation produced nothing: the watch went silent"
    );
}

#[test]
fn a_metadata_change_that_keeps_access_is_not_a_revocation() {
    // The control for the two tests above: an IN_ATTRIB on the root that leaves
    // this process able to use it must not be reported as a loss.
    let root = tempfile::tempdir().expect("temp dir");
    let _restore = Restore(root.path());
    let events = stream(FilesystemSensor::watch(root.path()).expect("watch"));

    fs::set_permissions(root.path(), Permissions::from_mode(0o750)).expect("chmod");
    fs::write(root.path().join("still-mine.md"), b"x").expect("write");

    let deadline = std::time::Instant::now() + DEADLINE;
    loop {
        let remaining = deadline.saturating_duration_since(std::time::Instant::now());
        match next_within(&events, remaining) {
            Some(Seen::Observed(paths))
                if paths
                    .iter()
                    .any(|p| p.file_name().and_then(|n| n.to_str()) == Some("still-mine.md")) =>
            {
                break;
            }
            Some(Seen::Observed(_)) => continue,
            Some(Seen::AccessLost(kind)) => {
                panic!("a chmod that keeps access was reported as a loss ({kind:?})")
            }
            None => panic!("the file written after a harmless chmod was never observed"),
        }
    }
}

#[test]
fn the_access_check_covers_both_read_and_search_permission() {
    let root = tempfile::tempdir().expect("temp dir");
    let _restore = Restore(root.path());

    assert!(check_access(root.path()).is_ok());

    // No read: the root cannot be listed.
    revoke(root.path(), 0o300);
    let denied = check_access(root.path()).expect_err("listing needs read permission");
    assert_eq!(denied.kind(), std::io::ErrorKind::PermissionDenied);

    // No search: the root can be listed, but nothing inside it can be reached.
    revoke(root.path(), 0o600);
    let denied = check_access(root.path()).expect_err("reaching inside needs search permission");
    assert_eq!(denied.kind(), std::io::ErrorKind::PermissionDenied);

    fs::set_permissions(root.path(), Permissions::from_mode(0o700)).expect("chmod");
    assert!(check_access(root.path()).is_ok());
}
