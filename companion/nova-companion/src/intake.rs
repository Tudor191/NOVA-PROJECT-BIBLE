//! The intake client — HTTP to `perception-engine`'s **existing** route.
//!
//! `POST /v1/perception/workspace-observations?source=<source>` with body
//! `{"path": "...", "observed_at": "<RFC3339>"}`. That contract was fixed by
//! 4F.2 and this slice does not alter it: 4F.3 is its first caller, not its
//! author. If the route ever proves insufficient, that is a finding to report,
//! not a contract to amend (TDD 4F.3 §7).
//!
//! **No `user_id` is sent, and there is no field for one.** The engine resolves
//! identity server-side from `Settings.primary_user_id` (ADR-025), and the
//! request model it validates against has no such field — so an identity cannot
//! be supplied here even by mistake.
//!
//! **No hashing happens here** (**D-4F3-2**). The real path goes on the wire to
//! the engine, which is the single authority that turns it into a handle. What
//! the ratification requires is that the raw path never reach the *persisted*
//! payload, the outbox row, the published event, or downstream world-model data
//! — all of which are on the engine's side of this call.

use std::path::Path;
use std::time::{Duration, SystemTime};

use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

pub const ROUTE: &str = "/v1/perception/workspace-observations";

/// What the engine said about one submission.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Submission {
    /// `202` — accepted. The engine's own body reports whether it published or
    /// deliberately did not (debounced, sensor paused, identity unconfigured);
    /// all of those are its decisions to make, and none is a client error.
    Accepted {
        published: bool,
        reason: Option<String>,
    },
    /// `404` — no sensor registered for this `source`. The honest answer until
    /// `sensors_by_source["filesystem"]` exists, so it is a named outcome
    /// rather than a generic failure.
    SourceNotRegistered,
    /// Any other status. Carried with the code so the caller can log it.
    Rejected { status: u16 },
}

#[derive(Debug)]
pub enum IntakeError {
    /// The engine was unreachable, or the request timed out. Expected during a
    /// restart, so the caller retries the *next* event rather than the process
    /// dying.
    Unreachable(String),
    /// The observation carried a timestamp that cannot be represented.
    /// **Never substituted with the current clock** — that would fabricate
    /// `observed_at`, which TDD 4F §20.1 forbids.
    UnrepresentableTimestamp,
}

impl std::fmt::Display for IntakeError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unreachable(detail) => {
                write!(formatter, "perception intake unreachable: {detail}")
            }
            Self::UnrepresentableTimestamp => {
                write!(
                    formatter,
                    "observation timestamp could not be represented as RFC3339"
                )
            }
        }
    }
}

impl std::error::Error for IntakeError {}

/// The exact request body 4F.2's `WorkspaceObservationRequest` validates.
///
/// Two fields, because that model has two. Built as JSON rather than through a
/// derived struct so the wire shape is visible in one place and cannot drift
/// behind a `#[serde(rename)]`.
pub fn request_body(
    path: &Path,
    observed_at: SystemTime,
) -> Result<serde_json::Value, IntakeError> {
    let observed_at = OffsetDateTime::from(observed_at)
        .format(&Rfc3339)
        .map_err(|_| IntakeError::UnrepresentableTimestamp)?;

    Ok(serde_json::json!({
        "path": path.to_string_lossy(),
        "observed_at": observed_at,
    }))
}

pub fn endpoint(base_url: &str) -> String {
    format!("{}{ROUTE}", base_url.trim_end_matches('/'))
}

pub struct IntakeClient {
    agent: ureq::Agent,
    base_url: String,
    source: String,
}

impl IntakeClient {
    pub fn new(base_url: impl Into<String>, source: impl Into<String>, timeout: Duration) -> Self {
        let config = ureq::Agent::config_builder()
            .timeout_global(Some(timeout))
            .build();
        Self {
            agent: config.into(),
            base_url: base_url.into(),
            source: source.into(),
        }
    }

    pub fn submit(&self, path: &Path, observed_at: SystemTime) -> Result<Submission, IntakeError> {
        let body = request_body(path, observed_at)?;
        let response = self
            .agent
            .post(&endpoint(&self.base_url))
            .query("source", &self.source)
            .send_json(&body);

        match response {
            Ok(mut ok) => {
                let parsed: serde_json::Value =
                    ok.body_mut().read_json().unwrap_or(serde_json::Value::Null);
                Ok(Submission::Accepted {
                    published: parsed
                        .get("published")
                        .and_then(serde_json::Value::as_bool)
                        .unwrap_or(false),
                    reason: parsed
                        .get("reason")
                        .and_then(serde_json::Value::as_str)
                        .map(str::to_string),
                })
            }
            Err(ureq::Error::StatusCode(404)) => Ok(Submission::SourceNotRegistered),
            Err(ureq::Error::StatusCode(status)) => Ok(Submission::Rejected { status }),
            Err(error) => Err(IntakeError::Unreachable(error.to_string())),
        }
    }
}
