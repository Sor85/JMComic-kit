# 禁漫下载工具

![Version](https://img.shields.io/badge/version-ver.1.0.1-skyblue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

将 GitHub Actions 的禁漫功能本地化，支持：
- **下载本子** - 批量下载禁漫本子到本地
- **导出收藏夹** - 导出收藏夹数据为 CSV 文件
- **Web 界面** - 现代化的 Web 界面，更直观易用
- **Rust 高性能下载器** - 🚀 降低 CPU/内存占用 70-90%，速度提升 2-3 倍

## 文件说明

### Web 界面（推荐）
- `web_server.py` - Web 服务器
- `web/` - 前端页面和静态资源
- `requirements-web.txt` - Web 依赖

### 命令行版本
#### 下载本子
- `local_download.py` - 下载脚本
- `local_download.yml` - 下载配置文件

#### 导出收藏夹
- `local_export_favorites.py` - 导出脚本
- `local_export_favorites.yml` - 导出配置文件

### Rust 高性能下载器
- `jmcomic-downloader/` - Rust 下载器源代码
- `bin/` - 编译好的二进制文件（Windows/Linux）

---

## 🚀 Rust 高性能下载器

### 工作原理

- **Python 侧**：负责 API 调用、认证、URL 解析（使用 jmcomic 库）
- **Rust 侧**：负责图片批量下载（异步 IO + 内存优化）
- **自动切换**：Rust 下载器不可用时自动降级到 Python 下载器

### 编译说明

如果需要重新编译（已提供预编译二进制，通常无需重新编译）：

**Windows:**
```bash
cd jmcomic-downloader
cargo build --release
copy target\release\jmcomic-downloader.exe ..\bin\jmcomic-downloader-windows.exe
```

**Linux (交叉编译):**
```bash
rustup target add x86_64-unknown-linux-gnu
cd jmcomic-downloader
cargo build --release --target x86_64-unknown-linux-gnu
cp target/x86_64-unknown-linux-gnu/release/jmcomic-downloader ../bin/jmcomic-downloader-linux
```

详细说明请参阅 [`jmcomic-downloader/README.md`](jmcomic-downloader/README.md)

---

## 快速开始

> **💡 网络优化提示**
> 
> 如果您在中国大陆地区使用，可能会遇到网络访问慢或安装依赖失败的问题。建议先更换系统软件源和 pip 镜像源：
> 
> **更换 Linux 系统软件源（推荐）：**
> ```bash
> bash <(curl -sSL https://linuxmirrors.cn/main.sh)
> ```
> 
> **更换 pip 镜像源：**
> ```bash
> pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
> ```
> 
> 详见：[LinuxMirrors - GNU/Linux 更换软件源脚本](https://github.com/SuperManito/LinuxMirrors)

### 方式一：Web 界面（推荐）

#### 第 1 步：安装依赖

```bash
pip install -r requirements-web.txt
```

#### 第 2 步：启动 Web 服务器

```bash
python web_server.py
```

#### 可选：日志容量运行参数（环境变量）

日志系统支持通过环境变量调优，不修改接口行为，仅影响日志保留与压缩策略。

| 变量名 | 默认值 | 作用 |
|------|------|------|
| `MAX_LOGS_PER_TASK` | `200` | 每个任务最多保留多少条日志 |
| `MAX_LOGS_ON_DISK` | `20000` | 磁盘总日志最大保留条数 |
| `WAL_COMPACT_BATCH_SIZE` | `100` | 写入多少条增量日志后触发一次压缩合并 |

示例（macOS/Linux）：

```bash
export MAX_LOGS_PER_TASK=300
export MAX_LOGS_ON_DISK=50000
export WAL_COMPACT_BATCH_SIZE=200
python web_server.py
```

建议：
- 磁盘空间紧张：减小 `MAX_LOGS_ON_DISK`
- 需要更长排障历史：增大 `MAX_LOGS_PER_TASK`
- 写入频率很高：适当增大 `WAL_COMPACT_BATCH_SIZE`

以上变量在服务启动时读取，修改后需重启服务生效。

#### 第 3 步：访问界面

打开浏览器访问：http://localhost:5000

#### 关于 Cron 表达式

自动化功能使用 Cron 表达式设置同步间隔，格式：`分 时 日 月 星期`

**常用示例：**
- `0 */6 * * *` - 每6小时执行
- `0 2 * * *` - 每天凌晨2点执行
- `0 0 * * 0` - 每周日凌晨执行
- `0 0 1 * *` - 每月1号凌晨执行
- `*/30 * * * *` - 每30分钟执行

**在线生成器：** [crontab.guru](https://crontab.guru/)

---

### 方式二：命令行

#### 前置要求

1. **安装 Python**（3.7+，推荐 3.9+）
   - 下载：https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"

2. **安装依赖**
   ```bash
   pip install jmcomic -U
   ```

### 命令行：下载本子

#### 第 1 步：配置要下载的本子

编辑 `local_download.py`，在配置区域填写本子 ID：

```python
# ==================== 配置区域 ====================

# 要下载的本子ID（一行一个，支持JM前缀）
ALBUM_IDS = """
422866
123456
JM789012
"""

# 单独下载章节ID（可选）
PHOTO_IDS = """

"""

# 禁漫账号（可选，不登录也能下载大部分本子）
JM_USERNAME = ""
JM_PASSWORD = ""

# 下载目录
DOWNLOAD_DIR = "./download/"

# 客户端类型：api（推荐）或 html
CLIENT_IMPL = "api"

# 图片格式：.jpg 或 .png 或 .webp（留空表示不转换）
IMAGE_SUFFIX = ""

# ==================== 配置区域结束 ====================
```

#### 第 2 步：运行下载

```bash
python local_download.py
```

#### 下载结果

下载完成后，本子会保存在 `download/` 目录，按以下结构组织：
```
download/
├── [本子ID]_[作者]_[标题]/
│   ├── 第1话/
│   │   ├── 00001.jpg
│   │   ├── 00002.jpg
│   │   └── ...
│   └── 第2话/
│       └── ...
```

---

### 命令行：导出收藏夹

#### 第 1 步：配置账号密码

**方式一：代码中配置**（推荐）

编辑 `local_export_favorites.py`，在配置区域填写：

```python
# ==================== 配置区域 ====================
JM_USERNAME = "你的账号"
JM_PASSWORD = "你的密码"
ZIP_PASSWORD = "压缩密码"  # 可选
ENABLE_ZIP = True          # 是否压缩
# ==================== 配置区域结束 ====================
```

**方式二：运行时输入**

直接运行脚本，按提示输入账号密码。

#### 第 2 步：运行导出

```bash
python local_export_favorites.py
```

#### 导出结果

导出完成后，你会得到：
- `export/` - CSV 文件目录，每个收藏夹一个 CSV 文件
- `export_favorites.7z` - 压缩包（如果启用压缩）

CSV 文件可用 Excel 或任何文本编辑器打开，包含：
- 本子 ID、标题、作者、标签、分类等信息

---

## 高级配置

### 下载本子 - 高级选项

#### 目录层级规则

**命令行版本** - 在 `local_download.py` 中配置 `DIR_RULE`：

```python
# 默认规则（推荐）
DIR_RULE = "Bd_Aauthor_Atitle_Pindex"
# 结果：基础路径/作者/标题/章节索引
# 例如：./download/MANA/[MANA] 神里绫华 1/1/

# 只用标题
DIR_RULE = "Bd_Atitle_Pindex"
# 结果：基础路径/标题/章节索引

# 更多规则说明
# _ 表示目录层级分隔（相当于 /）
# Bd = 基础路径标记（必须在最前面，不可移动）
# Aauthor = 作者
# Atitle = 标题
# Pindex = 章节索引
# 更多变量请参考 jmcomic 文档
```

**Web 界面版本** - 在创建/编辑任务时配置：

- **手动下载**：在下载表单的"目录层级规则"输入框中配置
- **自动化任务**：在创建/编辑自动化任务表单中配置

### 规则语法

使用 `/` 分隔目录层级（Web 界面），使用 `_` 分隔目录层级（命令行配置文件）。

**基本格式：**
```
Axxx  # 表示本子(Album)的属性xxx
Pxxx  # 表示章节(Photo)的属性xxx
```

### 可用字段

#### 本子属性 (Axxx)

| 字段 | 说明 | 示例 |
|------|------|------|
| `Aid` | 本子ID | 422866 |
| `Atitle` | 本子标题 | [MANA] 神里绫华 1 |
| `Aauthor` | 第一作者 | MANA |
| `Aauthors` | 所有作者 | ['MANA'] |
| `Aauthoroname` | 作者+原标题 | [MANA] 本子名 |
| `Aidoname` | ID+原标题 | [422866] 本子名 |
| `Aoname` | 原标题（未净化） | [MANA] 神里绫华 1 |
| `Atags` | 标签列表 | ['同人誌', '原神'] |
| `Aworks` | 作品列表 | ['原神'] |
| `Aactors` | 登场人物 | ['神里绫华'] |
| `Adescription` | 描述 | - |
| `Apub_date` | 发布日期 | 2023-01-01 |
| `Aupdate_date` | 更新日期 | 2023-01-01 |
| `Alikes` | 点赞数 | 1K |
| `Aviews` | 观看数 | 40K |
| `Acomment_count` | 评论数 | 123 |
| `Apage_count` | 总页数 | 25 |

#### 章节属性 (Pxxx)

| 字段 | 说明 | 示例 |
|------|------|------|
| `Pid` | 章节ID | 422866 |
| `Ptitle` / `Pname` | 章节标题 | 第一话 |
| `Pindex` | 章节索引（从1开始） | 1 |
| `Pindextitle` | "第X話 标题"格式 | 第1話 第一话 |
| `Psort` | 排序值 | 1 |
| `Pauthor` | 作者 | MANA |
| `Ptags` | 标签 | ['同人誌'] |

### 使用示例

```
# 常用组合
Aauthor/Atitle/Pindex         # 作者/标题/章节索引（默认）
Atitle/Pindex                 # 标题/章节索引（简化版）
Aid/Pindex                    # 本子ID/章节索引
Aauthor/Aid/Pindex            # 作者/本子ID/章节索引

# 详细组合
Aauthor/Aworks/Atitle/Pindex  # 作者/作品/标题/章节索引
Aworks/Aactors/Atitle/Pindex  # 作品/角色/标题/章节索引

# 使用特殊字段
Aauthoroname/Pindextitle      # [作者]标题/第X話 章节名
Aidoname/Pindex               # [ID]标题/章节索引

# f-string 语法（高级）
(JM{Aid})-{Aauthor}/{Pindex}  # (JM422866)-MANA/1
{Aauthor}-{Atitle}/{Pindex}   # MANA-神里绫华 1/1
```

### 注意事项

- 使用 `/` 分隔目录层级（Web 界面）
- 使用 `_` 分隔目录层级（命令行配置文件）
- 字段名区分大小写：`Atitle` ✓ `atitle` ✗
- 支持 f-string 语法：用 `{}` 包裹字段名可以自由组合
- 更多详情请参考 [jmcomic 文档](https://jmcomic.readthedocs.io/)

#### 压缩功能

**Web 界面版本**：在手动下载或自动化任务中勾选"下载完成后自动压缩"

**配置选项：**
- **压缩格式**：ZIP 或 7z
- **压缩级别**：
  - 整本压缩：将整个本子压缩为一个文件
  - 分章压缩：每个章节单独压缩
- **压缩密码**：可选，为压缩包设置密码保护
- **压缩后删除原文件**：节省磁盘空间

**依赖库**：
```bash
pip install pyzipper py7zr
```

**使用场景：**
- 节省磁盘空间（通常可节省 30-50%）
- 方便整理和分享
- 加密保护隐私内容

#### 图片格式转换

```python
# 转换为 PNG（高质量，文件大）
IMAGE_SUFFIX = ".png"

# 转换为 WebP（高压缩，文件小）
IMAGE_SUFFIX = ".webp"

# 不转换（保持原始格式）
IMAGE_SUFFIX = ""
```

#### 客户端类型

```python
# API 客户端（推荐，速度快，免登录）
CLIENT_IMPL = "api"

# HTML 客户端（慢但稳定）
CLIENT_IMPL = "html"
```

#### 高级重试机制

本项目已内置高级重试机制，自动优化域名选择策略：

**工作原理：**
- 记录每个域名的失败次数
- 自动将成功率高的域名排在前面
- 跳过失败次数过多的域名
- 多轮轮询确保最大成功率

**配置说明**（已在 `local_download.yml` 中配置，无需手动设置）：
```yaml
plugins:
  after_init:
    - plugin: advanced_retry
      kwargs:
        retry_config:
          retry_rounds: 3              # 最多轮询3轮所有域名
          retry_domain_max_times: 5    # 单个域名失败5次后跳过
```

**效果：**
- 自动学习哪些域名好用
- 减少在不稳定域名上浪费的时间
- 提高下载成功率

### 导出收藏夹 - 高级选项

编辑 `local_export_favorites.yml` 配置文件：

```yaml
plugins:
  main:
    - plugin: favorite_folder_export
      kwargs:
        save_dir: ./export/              # 导出目录
        zip_enable: true                 # 是否压缩
        zip_filepath: ./export.7z        # 压缩文件路径
        zip_password: ${ZIP_PASSWORD}    # 压缩密码
        delete_original_file: false      # 压缩后是否删除原文件
```

---

## 更多资源

### 原项目

- **GitHub**: https://github.com/hect0x7/JMComic-Crawler-Python
- **文档**: https://jmcomic.readthedocs.io/
- **教程**: 查看原项目的 `assets/docs/sources/tutorial/` 目录

### 网络优化工具

- **LinuxMirrors** - GNU/Linux 更换软件源脚本
  - GitHub: https://github.com/SuperManito/LinuxMirrors
  - 官网: https://linuxmirrors.cn
  - 一键更换系统软件源和 Docker 镜像源
  - 支持 30+ 种主流 Linux 发行版

### 配置文件语法

详细的配置文件语法说明：
https://jmcomic.readthedocs.io/zh-cn/latest/option_file_syntax/

---

## 致谢

本工具基于 [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) 项目开发。

感谢原作者 **hect0x7** 提供的优秀框架！

---

## 许可证

本工具基于原项目开发，遵循原项目的许可证。
