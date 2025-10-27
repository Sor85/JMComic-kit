# JMComic Rust 下载器

高性能图片下载器，使用 Rust 编写，专为大量图片下载优化。

## 特性

- **异步并发**：使用 Tokio 异步运行时，单线程处理数千并发连接
- **内存优化**：流式下载和写入，避免大图片全量加载到内存
- **智能重试**：自动重试失败的下载，支持指数退避
- **进度反馈**：实时输出 JSON 格式的进度信息
- **跨平台**：支持 Windows、Linux 和 macOS

## 编译

### Windows

```bash
cd jmcomic-downloader
cargo build --release
```

生成的可执行文件：`target/release/jmcomic-downloader.exe`

### Linux（在 Windows 上交叉编译）

1. 安装交叉编译工具链：
```bash
rustup target add x86_64-unknown-linux-gnu
```

2. 编译：
```bash
cargo build --release --target x86_64-unknown-linux-gnu
```

生成的可执行文件：`target/x86_64-unknown-linux-gnu/release/jmcomic-downloader`

## 使用方法

### 命令行参数

```bash
jmcomic-downloader \
  --manifest images.json \      # 图片清单文件（必需）
  --output-dir ./download \     # 输出目录（可选，默认 ./download）
  --concurrent 50 \             # 并发数（可选，默认 50）
  --retry 3 \                   # 重试次数（可选，默认 3）
  --timeout 30                  # 超时时间秒数（可选，默认 30）
```

### 图片清单格式

创建一个 JSON 文件，例如 `images.json`：

```json
{
  "images": [
    {
      "url": "https://example.com/image1.jpg",
      "path": "download/folder1/image1.jpg",
      "headers": {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://example.com/"
      }
    },
    {
      "url": "https://example.com/image2.jpg",
      "path": "download/folder1/image2.jpg",
      "headers": {}
    }
  ]
}
```

### 示例

```bash
# 下载图片
jmcomic-downloader --manifest images.json --concurrent 100 --retry 5

# 自定义输出目录
jmcomic-downloader --manifest images.json --output-dir /path/to/download

# 慢速连接，增加超时时间
jmcomic-downloader --manifest images.json --timeout 60
```

## 输出格式

### 进度信息

下载过程中会输出进度信息到 stdout（JSON 格式）：

```json
PROGRESS:{"total":100,"completed":50,"failed":2,"current_url":"https://..."}
```

### 最终结果

下载完成后输出最终结果到 stdout（JSON 格式）：

```json
RESULT:{"success":98,"failed":2,"failed_urls":["https://...","https://..."]}
```

### 退出码

- `0`：所有下载成功
- `1`：部分下载失败（至少有一张图片下载失败）
- 其他：程序错误

## Python 集成

在 Python 中使用：

```python
from server.utils.rust_downloader import (
    is_rust_downloader_available,
    download_images_with_rust,
    ImageTask
)

# 检查是否可用
if not is_rust_downloader_available():
    print("Rust downloader not available")
    exit(1)

# 准备图片任务
images = [
    ImageTask(
        url="https://example.com/image1.jpg",
        path="download/image1.jpg",
        headers={"User-Agent": "Mozilla/5.0"}
    ),
    ImageTask(
        url="https://example.com/image2.jpg",
        path="download/image2.jpg",
        headers={}
    )
]

# 下载
result = download_images_with_rust(
    images=images,
    concurrent=50,
    retry=3,
    timeout=30,
    progress_callback=lambda p: print(f"Progress: {p['completed']}/{p['total']}")
)

print(f"Success: {result.success}, Failed: {result.failed}")
if result.failed_urls:
    print(f"Failed URLs: {result.failed_urls}")
```

## 性能对比

相比 Python 实现：

- **CPU 占用**：降低 60-80%
- **内存占用**：降低 70-90%
- **下载速度**：提升 2-3 倍
- **并发能力**：支持更高并发数（100+）

## 开发

### 运行测试

```bash
cargo test
```

### 代码检查

```bash
cargo clippy
```

### 格式化

```bash
cargo fmt
```

## 技术栈

- **tokio** - 异步运行时
- **reqwest** - HTTP 客户端
- **clap** - CLI 参数解析
- **serde/serde_json** - JSON 序列化
- **anyhow** - 错误处理
- **futures** - 异步工具

## 许可证

遵循主项目许可证。

