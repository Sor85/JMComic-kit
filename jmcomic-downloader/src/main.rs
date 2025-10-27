mod config;
mod descramble;
mod downloader;
mod retry;

use anyhow::{Context, Result};
use clap::Parser;
use config::{DownloadConfig, ImageManifest};
use downloader::Downloader;
use std::fs;

#[derive(Parser, Debug)]
#[command(author, version, about = "High-performance image downloader for JMComic", long_about = None)]
struct Args {
    /// Path to the image manifest JSON file
    #[arg(short, long)]
    manifest: String,

    /// Output directory for downloaded images
    #[arg(short, long, default_value = "./download")]
    output_dir: String,

    /// Number of concurrent downloads
    #[arg(short, long, default_value_t = 50)]
    concurrent: usize,

    /// Number of retry attempts for failed downloads
    #[arg(short, long, default_value_t = 3)]
    retry: usize,

    /// Request timeout in seconds
    #[arg(short, long, default_value_t = 30)]
    timeout: u64,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();

    // Read manifest file
    let manifest_content = fs::read_to_string(&args.manifest)
        .with_context(|| format!("Failed to read manifest file: {}", args.manifest))?;

    let manifest: ImageManifest = serde_json::from_str(&manifest_content)
        .context("Failed to parse manifest JSON")?;

    if manifest.images.is_empty() {
        eprintln!("Warning: No images in manifest");
        return Ok(());
    }

    // Create download config
    let config = DownloadConfig {
        concurrent: args.concurrent,
        retry: args.retry,
        timeout: args.timeout,
        output_dir: args.output_dir,
    };

    // Create downloader
    let downloader = Downloader::new(config)?;

    // Start downloads
    eprintln!("Starting download of {} images...", manifest.images.len());
    eprintln!("Concurrent: {}, Retry: {}, Timeout: {}s", 
        args.concurrent, args.retry, args.timeout);

    let result = downloader.download_all(manifest.images).await?;

    // Output final result as JSON to stdout
    let result_json = serde_json::to_string(&result)?;
    println!("RESULT:{}", result_json);

    // Also print summary to stderr for human readability
    eprintln!("\nDownload completed:");
    eprintln!("  Success: {}", result.success);
    eprintln!("  Failed: {}", result.failed);

    if !result.failed_urls.is_empty() {
        eprintln!("\nFailed URLs:");
        for url in &result.failed_urls {
            eprintln!("  - {}", url);
        }
    }

    // Exit with non-zero code if any downloads failed
    if result.failed > 0 {
        std::process::exit(1);
    }

    Ok(())
}
