use std::time::Duration;
use tokio::time::sleep;

#[derive(Clone)]
pub struct RetryStrategy {
    max_retries: usize,
    base_delay_ms: u64,
    use_backoff: bool,
}

impl RetryStrategy {
    pub fn new(max_retries: usize, base_delay_ms: u64, use_backoff: bool) -> Self {
        Self {
            max_retries,
            base_delay_ms,
            use_backoff,
        }
    }

    pub fn max_retries(&self) -> usize {
        self.max_retries
    }

    pub async fn wait(&self, attempt: usize) {
        let delay = if self.use_backoff {
            self.base_delay_ms * (1 << attempt.min(5)) // Cap at 32x
        } else {
            self.base_delay_ms
        };
        sleep(Duration::from_millis(delay)).await;
    }
}

impl Default for RetryStrategy {
    fn default() -> Self {
        Self::new(3, 1000, true)
    }
}

// Unused but kept for future use
#[allow(dead_code)]
pub fn is_retryable_error(err: &reqwest::Error) -> bool {
    err.is_timeout() 
        || err.is_connect() 
        || err.is_request()
        || (err.status().map_or(false, |s| s.is_server_error()))
}

