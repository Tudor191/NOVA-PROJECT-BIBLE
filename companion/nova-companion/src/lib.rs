//! `nova-companion`'s library half.
//!
//! The binary is a thin `main` over these modules. They live in a library
//! target so the integration tests under `tests/` can drive them directly —
//! Rust integration tests cannot import a binary crate, and the alternative
//! (testing only through the process) would make the intake contract
//! unassertable without spawning a subprocess.
//!
//! What the companion is, and is not, is documented on `main.rs`.

pub mod config;
pub mod intake;
pub mod observability;
