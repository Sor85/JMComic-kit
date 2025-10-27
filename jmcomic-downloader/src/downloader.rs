use crate::config::{DownloadConfig, DownloadProgress, DownloadResult, ImageTask};
use crate::retry::RetryStrategy;
use anyhow::{Context, Result, bail};
use futures::StreamExt;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use tokio::fs::{self, File};
use tokio::io::AsyncWriteExt;
use tokio::sync::Semaphore;

pub struct Downloader {
    client: reqwest::Client,
    config: DownloadConfig,
    retry_strategy: RetryStrategy,
}

impl Downloader {
    pub fn new(config: DownloadConfig) -> Result<Self> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(config.timeout))
            .pool_max_idle_per_host(config.concurrent)
            .build()
            .context("Failed to create HTTP client")?;

        let retry_strategy = RetryStrategy::new(config.retry, 1000, true);

        Ok(Self {
            client,
            config,
            retry_strategy,
        })
    }

    pub async fn download_all(&self, tasks: Vec<ImageTask>) -> Result<DownloadResult> {
        let total = tasks.len();
        let completed = Arc::new(AtomicUsize::new(0));
        let failed = Arc::new(AtomicUsize::new(0));
        let semaphore = Arc::new(Semaphore::new(self.config.concurrent));
        let failed_urls = Arc::new(tokio::sync::Mutex::new(Vec::new()));

        let mut handles = vec![];

        for task in tasks {
            let client = self.client.clone();
            let retry_strategy = self.retry_strategy.clone();
            let completed = Arc::clone(&completed);
            let failed = Arc::clone(&failed);
            let semaphore = Arc::clone(&semaphore);
            let failed_urls = Arc::clone(&failed_urls);

            let handle = tokio::spawn(async move {
                let _permit = semaphore.acquire().await.unwrap();

                match download_with_retry(&client, &task, &retry_strategy).await {
                    Ok(_) => {
                        completed.fetch_add(1, Ordering::Relaxed);
                    }
                    Err(e) => {
                        eprintln!("Failed to download {}: {}", task.url, e);
                        failed.fetch_add(1, Ordering::Relaxed);
                        failed_urls.lock().await.push(task.url.clone());
                    }
                }

                // Report progress
                let current_completed = completed.load(Ordering::Relaxed);
                let current_failed = failed.load(Ordering::Relaxed);
                let progress = DownloadProgress {
                    total,
                    completed: current_completed,
                    failed: current_failed,
                    current_url: Some(task.url.clone()),
                };
                
                if let Ok(json) = serde_json::to_string(&progress) {
                    println!("PROGRESS:{}", json);
                }
            });

            handles.push(handle);
        }

        // Wait for all downloads to complete
        for handle in handles {
            let _ = handle.await;
        }

        let final_failed_urls = failed_urls.lock().await.clone();

        Ok(DownloadResult {
            success: completed.load(Ordering::Relaxed),
            failed: failed.load(Ordering::Relaxed),
            failed_urls: final_failed_urls,
        })
    }
}

async fn download_with_retry(
    client: &reqwest::Client,
    task: &ImageTask,
    retry_strategy: &RetryStrategy,
) -> Result<()> {
    let mut last_error = None;

    for attempt in 0..=retry_strategy.max_retries() {
        if attempt > 0 {
            retry_strategy.wait(attempt - 1).await;
        }

        match download_single(client, task).await {
            Ok(_) => {
                // 下载成功后，尝试解密图片
                if let Some(scramble_id) = task.scramble_id {
                    if let Err(e) = crate::descramble::descramble_image_auto(
                        &task.path,
                        scramble_id,
                        &task.url,
                    ) {
                        eprintln!("Warning: Failed to descramble image {}: {}", task.path, e);
                        // 解密失败不影响下载结果，仅打印警告
                    }
                }
                return Ok(());
            }
            Err(e) => {
                last_error = Some(e);
            }
        }
    }

    bail!("Failed after {} retries: {}", retry_strategy.max_retries(), last_error.unwrap())
}

async fn download_single(client: &reqwest::Client, task: &ImageTask) -> Result<()> {
    // Prepare request with headers
    let mut request = client.get(&task.url);
    
    for (key, value) in &task.headers {
        request = request.header(key, value);
    }

    // Send request
    let response = request.send().await
        .context("Failed to send request")?;
    
    let status = response.status();
    if !status.is_success() {
        bail!("HTTP {}", status);
    }

    // Create parent directory if needed
    if let Some(parent) = Path::new(&task.path).parent() {
        fs::create_dir_all(parent).await
            .context("Failed to create directory")?;
    }

    // Write to temporary file first
    let temp_path = format!("{}.tmp", task.path);
    let mut file = File::create(&temp_path).await
        .context("Failed to create file")?;

    // Stream download with chunked writes
    let mut stream = response.bytes_stream();
    
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("Failed to read chunk")?;
        file.write_all(&chunk).await
            .context("Failed to write to file")?;
    }

    file.flush().await
        .context("Failed to flush file")?;

    drop(file);

    // Rename temp file to final file
    fs::rename(&temp_path, &task.path).await
        .context("Failed to rename file")?;

    Ok(())
}

