//! **D1, end to end: the real `nova-companion` process detects a real
//! revocation of its watched root and reports it on the one internal route**
//! (TDD 4F.8 §29.1 A-4F8-1 (a), (a1), (a2); §29.5 item 1).
//!
//! The process is the shipped binary, configured by environment exactly as the
//! image is. The server is a real TCP listener that records every request, so
//! what the companion sent is asserted against bytes.
//!
//! **These tests must run as a non-root user**, for the reason
//! `sensors/tests/revocation.rs` gives: root bypasses permission checks, so a
//! `chmod` would deny it nothing. The revocation step asserts that the OS
//! really denies access, and fails loudly if it does not.

use std::fs::{self, Permissions};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime};

use nova_companion::intake::{IntakeClient, REVOCATION_ROUTE, ROUTE, RevocationReceipt};

const DEADLINE: Duration = Duration::from_secs(15);
/// The window over which a test shows that nothing more was sent.
const QUIET: Duration = Duration::from_secs(2);

#[derive(Debug, Clone)]
struct Captured {
    target: String,
    body: serde_json::Value,
}

impl Captured {
    fn is_revocation(&self) -> bool {
        self.target.starts_with(REVOCATION_ROUTE)
    }

    fn observed_file(&self) -> Option<String> {
        if !self.target.starts_with(ROUTE) {
            return None;
        }
        let path = self.body.get("path")?.as_str()?;
        Some(Path::new(path).file_name()?.to_string_lossy().into_owned())
    }
}

/// A real HTTP server that answers every request, in order, from `script`
/// (repeating its last line), and records each one.
fn server(script: Vec<(&'static str, &'static str)>) -> (String, Receiver<Captured>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().expect("addr").port();
    let (sender, receiver) = channel();
    let script = Arc::new(Mutex::new(script));

    thread::spawn(move || {
        for stream in listener.incoming().flatten() {
            let mut script = script.lock().expect("script");
            let (status, body) = if script.len() > 1 {
                script.remove(0)
            } else {
                script[0]
            };
            drop(script);
            serve_one(stream, status, body, &sender);
        }
    });
    (format!("http://127.0.0.1:{port}"), receiver)
}

/// A per-route variant: observations always get `observation`, and revocation
/// reports are answered from `revocations` in order.
fn routed_server(
    observation: (&'static str, &'static str),
    revocations: Vec<(&'static str, &'static str)>,
) -> (String, Receiver<Captured>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().expect("addr").port();
    let (sender, receiver) = channel();
    let revocations = Arc::new(Mutex::new(revocations));

    thread::spawn(move || {
        for stream in listener.incoming().flatten() {
            let revocations = Arc::clone(&revocations);
            let sender = sender.clone();
            serve_routed(stream, observation, &revocations, &sender);
        }
    });
    (format!("http://127.0.0.1:{port}"), receiver)
}

fn read_request(stream: &TcpStream) -> (String, serde_json::Value) {
    let mut reader = BufReader::new(stream.try_clone().expect("clone"));
    let mut request_line = String::new();
    reader.read_line(&mut request_line).expect("request line");
    let target = request_line
        .split_whitespace()
        .nth(1)
        .unwrap_or_default()
        .to_string();

    let mut content_length = 0usize;
    loop {
        let mut header = String::new();
        reader.read_line(&mut header).expect("header");
        if header.trim().is_empty() {
            break;
        }
        if let Some(value) = header.to_ascii_lowercase().strip_prefix("content-length:") {
            content_length = value.trim().parse().unwrap_or(0);
        }
    }
    let mut payload = vec![0u8; content_length];
    reader.read_exact(&mut payload).expect("body");
    let body = serde_json::from_slice(&payload).unwrap_or(serde_json::Value::Null);
    (target, body)
}

fn respond(mut stream: TcpStream, status: &str, body: &str) {
    let response = format!(
        "{status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
}

fn serve_one(stream: TcpStream, status: &str, body: &str, sender: &Sender<Captured>) {
    let (target, request_body) = read_request(&stream);
    let _ = sender.send(Captured {
        target,
        body: request_body,
    });
    respond(stream, status, body);
}

fn serve_routed(
    stream: TcpStream,
    observation: (&'static str, &'static str),
    revocations: &Mutex<Vec<(&'static str, &'static str)>>,
    sender: &Sender<Captured>,
) {
    let (target, request_body) = read_request(&stream);
    let (status, body) = if target.starts_with(REVOCATION_ROUTE) {
        let mut script = revocations.lock().expect("script");
        if script.len() > 1 {
            script.remove(0)
        } else {
            script[0]
        }
    } else {
        observation
    };
    let _ = sender.send(Captured {
        target,
        body: request_body,
    });
    respond(stream, status, body);
}

const OBSERVED: (&str, &str) = (
    "HTTP/1.1 202 Accepted",
    r#"{"sensor_id":"companion-filesystem","published":true}"#,
);
const ACKNOWLEDGED: (&str, &str) = (
    "HTTP/1.1 202 Accepted",
    r#"{"sensor_id":"companion-filesystem","state":"failed","transitioned":true}"#,
);
const UNAVAILABLE: (&str, &str) = ("HTTP/1.1 503 Service Unavailable", r#"{}"#);

/// The real binary, watching `root` and reporting to `base_url`.
struct Companion(Child);

impl Companion {
    fn start(root: &Path, base_url: &str) -> (Self, Receiver<String>) {
        let mut child = Command::new(env!("CARGO_BIN_EXE_nova-companion"))
            .env_clear()
            .env("NOVA_COMPANION_WATCH_ROOT", root)
            .env("NOVA_COMPANION_PERCEPTION_BASE_URL", base_url)
            .env("NOVA_COMPANION_SOURCE", "filesystem")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("spawn the companion");

        let (sender, logs) = channel();
        let stdout = child.stdout.take().expect("stdout");
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if sender.send(line).is_err() {
                    return;
                }
            }
        });
        let companion = Self(child);
        wait_for_log(&logs, "nova-companion starting");
        (companion, logs)
    }
}

impl Drop for Companion {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn wait_for_log(logs: &Receiver<String>, message: &str) -> serde_json::Value {
    let deadline = Instant::now() + DEADLINE;
    while let Some(remaining) = deadline.checked_duration_since(Instant::now()) {
        let Ok(line) = logs.recv_timeout(remaining) else {
            break;
        };
        let parsed: serde_json::Value = serde_json::from_str(&line).unwrap_or_default();
        if parsed.get("message").and_then(|m| m.as_str()) == Some(message) {
            return parsed;
        }
    }
    panic!("the companion never logged {message:?}");
}

/// Every request received until `until` holds or the deadline passes.
fn collect_until(
    received: &Receiver<Captured>,
    seen: &mut Vec<Captured>,
    until: impl Fn(&[Captured]) -> bool,
) {
    let deadline = Instant::now() + DEADLINE;
    while !until(seen) {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .unwrap_or_else(|| panic!("timed out; received so far: {seen:?}"));
        match received.recv_timeout(remaining) {
            Ok(captured) => seen.push(captured),
            Err(_) => panic!("timed out; received so far: {seen:?}"),
        }
    }
}

/// Everything received over the next `QUIET` window.
fn drain_quiet(received: &Receiver<Captured>, seen: &mut Vec<Captured>) {
    let deadline = Instant::now() + QUIET;
    while let Some(remaining) = deadline.checked_duration_since(Instant::now()) {
        match received.recv_timeout(remaining) {
            Ok(captured) => seen.push(captured),
            Err(_) => return,
        }
    }
}

struct Restore<'a>(&'a Path);

impl Drop for Restore<'_> {
    fn drop(&mut self) {
        let _ = fs::set_permissions(self.0, Permissions::from_mode(0o755));
    }
}

/// Mode 0o300: the owner keeps write and search, so this test can still create
/// files inside the root, but loses read, so the root can no longer be listed.
fn revoke(root: &Path) {
    fs::set_permissions(root, Permissions::from_mode(0o300)).expect("chmod");
    assert!(
        fs::read_dir(root).is_err(),
        "the OS still grants read after chmod 300. These tests must run as a non-root \
         user: root bypasses permission checks, so nothing here would be tested"
    );
}

fn written(seen: &[Captured], name: &str) -> bool {
    seen.iter()
        .any(|c| c.observed_file().as_deref() == Some(name))
}

// --- the report's wire shape ---------------------------------------------------

#[test]
fn the_report_goes_to_the_revocation_route_with_the_source_and_only_a_detection_time() {
    let (base_url, received) = server(vec![ACKNOWLEDGED]);
    let client = IntakeClient::new(&base_url, "filesystem", Duration::from_secs(5));

    let receipt = client
        .report_revocation(SystemTime::UNIX_EPOCH)
        .expect("report");
    assert_eq!(
        receipt,
        RevocationReceipt::Acknowledged {
            state: "failed".into(),
            transitioned: true
        }
    );

    let captured = received
        .recv_timeout(Duration::from_secs(5))
        .expect("captured");
    assert_eq!(
        captured.target,
        format!("{REVOCATION_ROUTE}?source=filesystem")
    );
    let object = captured.body.as_object().expect("object body");
    assert_eq!(
        object.keys().collect::<Vec<_>>(),
        vec!["detected_at"],
        "the report carries exactly one field: no path, no identity"
    );
    assert!(
        object["detected_at"]
            .as_str()
            .is_some_and(|value| value.starts_with("1970-01-01T00:00:00")),
        "the detection time travels unmodified: {object:?}"
    );
}

#[test]
fn an_unregistered_source_and_a_server_error_are_distinct_outcomes() {
    let (base_url, _received) = server(vec![("HTTP/1.1 404 Not Found", "{}")]);
    let client = IntakeClient::new(&base_url, "filesystem", Duration::from_secs(5));
    assert_eq!(
        client
            .report_revocation(SystemTime::UNIX_EPOCH)
            .expect("report"),
        RevocationReceipt::SourceNotRegistered
    );

    let (base_url, _received) = server(vec![UNAVAILABLE]);
    let client = IntakeClient::new(&base_url, "filesystem", Duration::from_secs(5));
    assert_eq!(
        client
            .report_revocation(SystemTime::UNIX_EPOCH)
            .expect("report"),
        RevocationReceipt::Rejected { status: 503 }
    );
}

// --- the real process -----------------------------------------------------------

#[test]
fn the_real_companion_reports_a_real_revocation_once_and_then_submits_nothing() {
    let root = tempfile::tempdir().expect("temp dir");
    let _restore = Restore(root.path());
    let (base_url, received) = routed_server(OBSERVED, vec![ACKNOWLEDGED]);
    let (_companion, logs) = Companion::start(root.path(), &base_url);
    let mut seen = Vec::new();

    // Before: an ordinary observation, so the run loop is known to be live.
    fs::write(root.path().join("before.md"), b"before").expect("write");
    collect_until(&received, &mut seen, |s| written(s, "before.md"));

    revoke(root.path());
    collect_until(&received, &mut seen, |s| {
        s.iter().any(Captured::is_revocation)
    });
    let revoked = wait_for_log(&logs, "permission_revoked");
    assert!(
        !revoked
            .to_string()
            .contains(&*root.path().to_string_lossy()),
        "the revocation log named the watched path: {revoked}"
    );
    wait_for_log(&logs, "revocation_reported");

    // After: a write by a writer that still has permission. The watch still
    // delivers it (F-4F8-7), and the companion submits nothing for it and does
    // not report again, because the engine acknowledged the first report.
    fs::write(root.path().join("after.md"), b"after").expect("write");
    drain_quiet(&received, &mut seen);

    assert!(
        !written(&seen, "after.md"),
        "an observation was submitted after the revocation: {seen:?}"
    );
    assert_eq!(
        seen.iter().filter(|c| c.is_revocation()).count(),
        1,
        "an acknowledged revocation was reported again: {seen:?}"
    );
}

#[test]
fn an_unacknowledged_report_is_sent_again_on_the_next_event() {
    let root = tempfile::tempdir().expect("temp dir");
    let _restore = Restore(root.path());
    let (base_url, received) = routed_server(OBSERVED, vec![UNAVAILABLE, ACKNOWLEDGED]);
    let (_companion, logs) = Companion::start(root.path(), &base_url);
    let mut seen = Vec::new();

    revoke(root.path());
    collect_until(&received, &mut seen, |s| {
        s.iter().any(Captured::is_revocation)
    });
    wait_for_log(&logs, "revocation_rejected");

    // No timer resends it. The next event does, as a failed submission's next
    // event would.
    fs::write(root.path().join("nudge.md"), b"x").expect("write");
    collect_until(&received, &mut seen, |s| {
        s.iter().filter(|c| c.is_revocation()).count() == 2
    });
    wait_for_log(&logs, "revocation_reported");
    assert!(
        !written(&seen, "nudge.md"),
        "submitted after the revocation: {seen:?}"
    );
}
