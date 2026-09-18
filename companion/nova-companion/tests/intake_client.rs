//! **S-2: the event is submitted through the existing intake route, unchanged.**
//!
//! Exercised against a **real TCP server** on a loopback port, written from the
//! standard library rather than pulled in as a test dependency. It records the
//! exact request line, query and body, so "we did not change the contract" is
//! asserted against bytes rather than against intent.
//!
//! A mocked client would prove only that the mock was called. TDD 4F.3 §11.1
//! asks for the client to be driven against a stub *server*, and the
//! instruction for this slice forbids satisfying S-2 with mocks alone.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::Path;
use std::sync::mpsc::{Sender, channel};
use std::thread;
use std::time::{Duration, SystemTime};

/// What the stub actually received.
#[derive(Debug, Clone)]
struct Captured {
    method: String,
    target: String,
    body: String,
}

/// A one-request stub server. Returns its base URL and a channel carrying what
/// it saw.
fn stub(
    status_line: &'static str,
    response_body: &'static str,
) -> (String, std::sync::mpsc::Receiver<Captured>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().expect("addr").port();
    let (sender, receiver) = channel();

    thread::spawn(move || {
        if let Ok((stream, _)) = listener.accept() {
            serve_one(stream, status_line, response_body, &sender);
        }
    });

    (format!("http://127.0.0.1:{port}"), receiver)
}

fn serve_one(mut stream: TcpStream, status_line: &str, body: &str, sender: &Sender<Captured>) {
    let mut reader = BufReader::new(stream.try_clone().expect("clone"));

    let mut request_line = String::new();
    reader.read_line(&mut request_line).expect("request line");
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or_default().to_string();
    let target = parts.next().unwrap_or_default().to_string();

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

    let _ = sender.send(Captured {
        method,
        target,
        body: String::from_utf8_lossy(&payload).into_owned(),
    });

    let response = format!(
        "{status_line}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
}

fn client(base_url: &str) -> nova_companion::intake::IntakeClient {
    nova_companion::intake::IntakeClient::new(base_url, "filesystem", Duration::from_secs(5))
}

const ACCEPTED: &str = "HTTP/1.1 202 Accepted";

#[test]
fn it_posts_to_the_existing_route_with_the_source_query() {
    let (base_url, received) = stub(ACCEPTED, r#"{"sensor_id":"fs","published":true}"#);
    let outcome = client(&base_url).submit(Path::new("/tmp/ada/notes.md"), SystemTime::UNIX_EPOCH);
    assert!(outcome.is_ok(), "submit failed: {outcome:?}");

    let captured = received
        .recv_timeout(Duration::from_secs(5))
        .expect("captured");
    assert_eq!(captured.method, "POST");
    assert!(
        captured
            .target
            .starts_with("/v1/perception/workspace-observations"),
        "posted to the wrong route: {}",
        captured.target
    );
    assert!(
        captured.target.contains("source=filesystem"),
        "source query missing: {}",
        captured.target
    );
}

#[test]
fn the_body_carries_exactly_the_two_fields_the_engine_validates() {
    // 4F.2's `WorkspaceObservationRequest` has exactly `path` and
    // `observed_at`. Sending a third would not be rejected -- Pydantic ignores
    // unknown keys -- so a *count* assertion is what keeps the contract honest.
    let (base_url, received) = stub(ACCEPTED, r#"{"published":true}"#);
    client(&base_url)
        .submit(Path::new("/tmp/ada/notes.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    let captured = received
        .recv_timeout(Duration::from_secs(5))
        .expect("captured");
    let parsed: serde_json::Value = serde_json::from_str(&captured.body).expect("json body");
    let object = parsed.as_object().expect("object body");

    assert_eq!(
        object.len(),
        2,
        "body carried unexpected fields: {object:?}"
    );
    assert_eq!(
        object.get("path").and_then(|v| v.as_str()),
        Some("/tmp/ada/notes.md")
    );
    assert!(object.contains_key("observed_at"));
}

#[test]
fn no_user_id_or_object_id_is_ever_sent() {
    // The identity boundary, from the client's side. The engine resolves
    // `user_id` server-side (ADR-025) and there is no field for one; this
    // asserts the companion never invents the keys.
    let (base_url, received) = stub(ACCEPTED, r#"{"published":true}"#);
    client(&base_url)
        .submit(Path::new("/tmp/ada/notes.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    let captured = received
        .recv_timeout(Duration::from_secs(5))
        .expect("captured");
    assert!(!captured.body.contains("user_id"));
    assert!(!captured.body.contains("object_id"));
}

#[test]
fn observed_at_is_rfc3339_and_is_not_the_current_time() {
    // TDD 4F §20.1: the timestamp travels unmodified. Submitting the epoch and
    // reading the epoch back proves no substitution happened.
    let (base_url, received) = stub(ACCEPTED, r#"{"published":true}"#);
    client(&base_url)
        .submit(Path::new("/tmp/a.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    let captured = received
        .recv_timeout(Duration::from_secs(5))
        .expect("captured");
    let parsed: serde_json::Value = serde_json::from_str(&captured.body).expect("json");
    let observed_at = parsed["observed_at"].as_str().expect("observed_at");

    assert!(
        observed_at.starts_with("1970-01-01T00:00:00"),
        "got {observed_at}"
    );
}

#[test]
fn a_404_is_reported_as_an_unregistered_source_not_a_generic_failure() {
    // The honest outcome until `sensors_by_source["filesystem"]` exists.
    let (base_url, _received) = stub("HTTP/1.1 404 Not Found", r#"{"detail":"no sensor"}"#);
    let outcome = client(&base_url)
        .submit(Path::new("/tmp/a.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    assert_eq!(
        outcome,
        nova_companion::intake::Submission::SourceNotRegistered
    );
}

#[test]
fn a_server_error_is_surfaced_with_its_status() {
    let (base_url, _received) = stub("HTTP/1.1 500 Internal Server Error", r#"{}"#);
    let outcome = client(&base_url)
        .submit(Path::new("/tmp/a.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    assert_eq!(
        outcome,
        nova_companion::intake::Submission::Rejected { status: 500 }
    );
}

#[test]
fn the_engines_own_not_published_reason_is_carried_through() {
    // The engine decides to debounce, or to drop because a sensor is paused.
    // Those are its decisions, and the client reports them rather than
    // treating them as its own failure.
    let (base_url, _received) = stub(ACCEPTED, r#"{"published":false,"reason":"debounced"}"#);
    let outcome = client(&base_url)
        .submit(Path::new("/tmp/a.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    assert_eq!(
        outcome,
        nova_companion::intake::Submission::Accepted {
            published: false,
            reason: Some("debounced".to_string())
        }
    );
}

#[test]
fn an_unreachable_engine_is_an_error_the_caller_can_survive() {
    // Nothing is listening on this port. The loop must keep running, so this
    // must be a returned error rather than a panic.
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().expect("addr").port();
    drop(listener);

    let outcome = client(&format!("http://127.0.0.1:{port}"))
        .submit(Path::new("/tmp/a.md"), SystemTime::UNIX_EPOCH);

    assert!(matches!(
        outcome,
        Err(nova_companion::intake::IntakeError::Unreachable(_))
    ));
}

#[test]
fn a_malformed_reply_body_does_not_break_the_client() {
    // A 202 with a body the client cannot parse still means accepted. Failing
    // here would turn the engine's cosmetic change into the companion's outage.
    let (base_url, _received) = stub(ACCEPTED, "not json at all");
    let outcome = client(&base_url)
        .submit(Path::new("/tmp/a.md"), SystemTime::UNIX_EPOCH)
        .expect("submit");

    assert_eq!(
        outcome,
        nova_companion::intake::Submission::Accepted {
            published: false,
            reason: None
        }
    );
}

#[test]
fn the_route_constant_matches_the_engines_registered_path() {
    assert_eq!(
        nova_companion::intake::ROUTE,
        "/v1/perception/workspace-observations"
    );
    assert_eq!(
        nova_companion::intake::endpoint("http://perception-engine:8000/"),
        "http://perception-engine:8000/v1/perception/workspace-observations"
    );
}
