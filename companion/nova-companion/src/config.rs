//! Configuration, from the environment only.
//!
//! Mirrors every engine's `pydantic-settings` convention — a `NOVA_COMPANION_`
//! prefix, one variable per setting, no config file — so an operator who has
//! configured an engine has already configured this.
//!
//! **Every setting that widens what is watched is required and has no default.**
//! `NOVA_COMPANION_WATCH_ROOT` in particular: a default would be a privacy
//! decision made by a default value, which **D-4F3-3** forbids.

use std::path::PathBuf;
use std::time::Duration;

#[derive(Debug, Clone)]
pub struct Config {
    /// The **one** directory watched. Required, no default (**D-4F3-3**).
    pub watch_root: PathBuf,
    /// Base URL of `perception-engine` on the internal network.
    pub perception_base_url: String,
    /// The `source` query value, which must match a key in the engine's
    /// `sensors_by_source`. Defaults to `filesystem` — the key 4F.3 registers.
    pub source: String,
    pub request_timeout: Duration,
}

#[derive(Debug)]
pub enum ConfigError {
    Missing(&'static str),
    Invalid { key: &'static str, reason: String },
}

impl std::fmt::Display for ConfigError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Missing(key) => write!(
                formatter,
                "{key} is required and has no default; refusing to guess what to watch"
            ),
            Self::Invalid { key, reason } => write!(formatter, "{key} is invalid: {reason}"),
        }
    }
}

impl std::error::Error for ConfigError {}

const WATCH_ROOT: &str = "NOVA_COMPANION_WATCH_ROOT";
const BASE_URL: &str = "NOVA_COMPANION_PERCEPTION_BASE_URL";
const SOURCE: &str = "NOVA_COMPANION_SOURCE";
const TIMEOUT_MS: &str = "NOVA_COMPANION_REQUEST_TIMEOUT_MS";

impl Config {
    pub fn from_env() -> Result<Self, ConfigError> {
        Self::from_lookup(|key| std::env::var(key).ok())
    }

    /// Injectable lookup so the rules below are testable without mutating the
    /// process environment, which would make these tests order-dependent.
    pub fn from_lookup(lookup: impl Fn(&str) -> Option<String>) -> Result<Self, ConfigError> {
        let watch_root = lookup(WATCH_ROOT)
            .filter(|value| !value.trim().is_empty())
            .ok_or(ConfigError::Missing(WATCH_ROOT))?;

        let perception_base_url = lookup(BASE_URL)
            .filter(|value| !value.trim().is_empty())
            .ok_or(ConfigError::Missing(BASE_URL))?;

        let request_timeout = match lookup(TIMEOUT_MS) {
            None => Duration::from_secs(5),
            Some(raw) => raw
                .trim()
                .parse::<u64>()
                .map(Duration::from_millis)
                .map_err(|error| ConfigError::Invalid {
                    key: TIMEOUT_MS,
                    reason: error.to_string(),
                })?,
        };

        Ok(Self {
            watch_root: PathBuf::from(watch_root.trim()),
            perception_base_url: perception_base_url.trim().trim_end_matches('/').to_string(),
            source: lookup(SOURCE)
                .filter(|value| !value.trim().is_empty())
                .unwrap_or_else(|| "filesystem".to_string()),
            request_timeout,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn lookup(pairs: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> + use<> {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect();
        move |key: &str| map.get(key).cloned()
    }

    const MINIMAL: &[(&str, &str)] = &[
        (WATCH_ROOT, "/workspace/project"),
        (BASE_URL, "http://perception-engine:8000"),
    ];

    #[test]
    fn a_missing_watch_root_is_refused_rather_than_defaulted() {
        // **D-4F3-3.** There is no fallback to the current directory or `$HOME`
        // -- a default here would decide what to watch on the operator's behalf.
        let error = Config::from_lookup(lookup(&[(BASE_URL, "http://x")])).unwrap_err();
        assert!(matches!(error, ConfigError::Missing(WATCH_ROOT)));
        assert!(error.to_string().contains("refusing to guess"));
    }

    #[test]
    fn a_blank_watch_root_is_treated_as_missing() {
        for blank in ["", "   "] {
            let error = Config::from_lookup(lookup(&[(WATCH_ROOT, blank), (BASE_URL, "http://x")]))
                .unwrap_err();
            assert!(matches!(error, ConfigError::Missing(WATCH_ROOT)));
        }
    }

    #[test]
    fn a_missing_base_url_is_refused() {
        let error = Config::from_lookup(lookup(&[(WATCH_ROOT, "/w")])).unwrap_err();
        assert!(matches!(error, ConfigError::Missing(BASE_URL)));
    }

    #[test]
    fn the_source_defaults_to_the_key_the_engine_registers() {
        let config = Config::from_lookup(lookup(MINIMAL)).expect("config");
        assert_eq!(config.source, "filesystem");
    }

    #[test]
    fn a_trailing_slash_on_the_base_url_does_not_double_up() {
        let config = Config::from_lookup(lookup(&[
            (WATCH_ROOT, "/w"),
            (BASE_URL, "http://perception-engine:8000/"),
        ]))
        .expect("config");
        assert_eq!(config.perception_base_url, "http://perception-engine:8000");
    }

    #[test]
    fn an_unparseable_timeout_is_an_error_not_a_silent_default() {
        let error = Config::from_lookup(lookup(&[
            (WATCH_ROOT, "/w"),
            (BASE_URL, "http://x"),
            (TIMEOUT_MS, "soon"),
        ]))
        .unwrap_err();
        assert!(matches!(
            error,
            ConfigError::Invalid {
                key: TIMEOUT_MS,
                ..
            }
        ));
    }

    #[test]
    fn the_timeout_has_a_default_because_it_widens_nothing() {
        let config = Config::from_lookup(lookup(MINIMAL)).expect("config");
        assert_eq!(config.request_timeout, Duration::from_secs(5));
    }
}
