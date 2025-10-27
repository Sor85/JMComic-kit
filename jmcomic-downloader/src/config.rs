use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Deserialize)]
pub struct ImageManifest {
    pub images: Vec<ImageTask>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ImageTask {
    pub url: String,
    pub path: String,
    #[serde(default)]
    pub headers: HashMap<String, String>,
    #[serde(default)]
    pub scramble_id: Option<u32>,
}

#[derive(Debug, Clone)]
pub struct DownloadConfig {
    pub concurrent: usize,
    pub retry: usize,
    pub timeout: u64,
    #[allow(dead_code)]
    pub output_dir: String,
}

impl Default for DownloadConfig {
    fn default() -> Self {
        Self {
            concurrent: 50,
            retry: 3,
            timeout: 30,
            output_dir: "./download".to_string(),
        }
    }
}

#[derive(Debug, Serialize)]
pub struct DownloadProgress {
    pub total: usize,
    pub completed: usize,
    pub failed: usize,
    pub current_url: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct DownloadResult {
    pub success: usize,
    pub failed: usize,
    pub failed_urls: Vec<String>,
}

