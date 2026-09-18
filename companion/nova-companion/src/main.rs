//! `nova-companion` — the Rust OS-level perception daemon.
//!
//! One job in 4F.3: watch **one explicitly configured directory**, and submit
//! each real change to `perception-engine`'s existing intake route. TDD 4F §7
//! fixes what it is, and every line of that boundary is load-bearing:
//!
//! - **No listening port.** It is a client, never a server. There is no HTTP
//!   server dependency in `Cargo.toml`, so this is structural rather than a
//!   convention.
//! - **No Event Bus.** It never connects to NATS, and has no client to do so.
//! - **No persistence.** It owns no store.
//! - **No actuators.** 4F.3 implements none; TDD 4F §7.3 puts them behind
//!   `action-engine` action types when they arrive.
//! - **No hashing, no `project_id`, no fusion.** All `perception-engine`'s
//!   (**D-4F3-2**) or a later slice's.
//!
//! **What this does not prove.** AC-7 is *not* met by this slice and is not
//! claimed. 4F.3 supplies the genuine OS event that starts AC-7's interval for
//! the first time; measuring that interval honestly is 4F.8's work (TDD 4F
//! §20.1).

use std::process::ExitCode;

use nova_companion::config::Config;
use nova_companion::intake::{self, IntakeClient, Submission};
use nova_companion::observability::{error, info, loggable_name, warning};
use nova_companion_sensors::FilesystemSensor;

const LOGGER: &str = "nova-companion";

fn main() -> ExitCode {
    let config = match Config::from_env() {
        Ok(config) => config,
        Err(problem) => {
            // Startup misconfiguration is the one place a path may be named:
            // it is the operator's own value, echoed back so they can fix it.
            error(
                LOGGER,
                "configuration_invalid",
                serde_json::json!({ "detail": problem.to_string() }),
            );
            return ExitCode::FAILURE;
        }
    };

    let sensor = match FilesystemSensor::watch(&config.watch_root) {
        Ok(sensor) => sensor,
        Err(problem) => {
            error(
                LOGGER,
                "watch_root_unusable",
                serde_json::json!({ "detail": problem.to_string() }),
            );
            return ExitCode::FAILURE;
        }
    };

    info(
        LOGGER,
        "nova-companion starting",
        serde_json::json!({
            // The root is named once, at startup, because an operator needs to
            // see what the process actually bound to. Per-event logs below
            // carry a file name only.
            "watch_root": sensor.root().display().to_string(),
            "source": config.source,
            "endpoint": intake::endpoint(&config.perception_base_url),
        }),
    );

    let client = IntakeClient::new(
        &config.perception_base_url,
        &config.source,
        config.request_timeout,
    );

    run(&sensor, &client);

    // Reached when the watcher's channel closes — a clean shutdown, not a
    // failure, so it exits successfully and says so.
    info(LOGGER, "nova-companion stopped", serde_json::json!({}));
    ExitCode::SUCCESS
}

/// The observe-and-submit loop.
///
/// Separated from `main` so it takes its collaborators as arguments and can be
/// driven in a test against a real watcher and a stub server.
///
/// **Every failure here is survivable.** An unreachable engine, a 404 for an
/// unregistered source, a 5xx — each is logged and the loop continues to the
/// next event. A perception daemon that exited because the engine restarted
/// would turn a momentary outage into a permanent one.
fn run(sensor: &FilesystemSensor, client: &IntakeClient) {
    while let Some(batch) = sensor.next_batch() {
        let observations = match batch {
            Ok(observations) => observations,
            Err(problem) => {
                warning(
                    LOGGER,
                    "watch_error",
                    serde_json::json!({ "detail": problem.to_string() }),
                );
                continue;
            }
        };

        for observation in observations {
            let name = loggable_name(&observation.path);
            match client.submit(&observation.path, observation.observed_at) {
                Ok(Submission::Accepted { published, reason }) => info(
                    LOGGER,
                    "observation_submitted",
                    serde_json::json!({ "file": name, "published": published, "reason": reason }),
                ),
                Ok(Submission::SourceNotRegistered) => warning(
                    LOGGER,
                    "source_not_registered",
                    serde_json::json!({ "file": name }),
                ),
                Ok(Submission::Rejected { status }) => warning(
                    LOGGER,
                    "observation_rejected",
                    serde_json::json!({ "file": name, "status": status }),
                ),
                Err(problem) => warning(
                    LOGGER,
                    "observation_not_submitted",
                    serde_json::json!({ "file": name, "detail": problem.to_string() }),
                ),
            }
        }
    }
}
