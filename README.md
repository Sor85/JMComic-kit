# 禁漫工具 - 本地运行版本

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

### 性能提升

使用 Rust 编写的下载器，专为大量图片下载优化：

| 指标 | Python 下载器 | Rust 下载器 | 提升 |
|------|--------------|------------|------|
| CPU 占用 | 60-80% | 10-20% | **降低 70-80%** |
| 内存占用 | 500-1000 MB | 50-100 MB | **降低 90%** |
| 下载速度 | 基准 | 2-3x | **提升 2-3 倍** |
| 并发能力 | 20-30 | 100+ | **提升 3-5 倍** |

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

#### 第 3 步：访问界面

打开浏览器访问：http://localhost:5000

在 Web 界面中你可以：
- **手动操作** - 下载本子或导出收藏夹数据，实时查看进度
- **自动化任务** - 定时同步收藏夹，自动下载新本子（跳过已有）
- **任务管理** - 查看任务进度、执行历史和实时日志
- **执行历史** - 每个任务保留最近 10 条执行记录，分页浏览
- **日志查看** - 手动任务日志分页显示（每页 10 条），支持筛选
- **统计面板** - 查看下载统计、成功率、本月新增等数据
- **CSV 导入** - 支持批量导入本子 ID，快速创建下载任务

#### 关于 Cron 表达式

自动化功能使用 Cron 表达式设置同步间隔，格式：`分 时 日 月 星期`

**常用示例：**
- `0 */6 * * *` - 每6小时执行
- `0 2 * * *` - 每天凌晨2点执行
- `0 0 * * 0` - 每周日凌晨执行
- `0 0 1 * *` - 每月1号凌晨执行
- `*/30 * * * *` - 每30分钟执行

**在线生成器：** [crontab.guru](https://crontab.guru/)

#### Web 界面功能详解

**任务页面** - 手动下载和导出
- 下载本子：输入本子/章节 ID，批量下载
- 导出收藏夹：输入账号信息，导出收藏数据
- CSV 批量导入：支持从 CSV 文件导入大量本子 ID
- 实时进度：查看当前运行任务的实时进度

**自动化页面** - 定时任务管理
- 创建任务：设置 Cron 表达式、账号、目录规则等
- 编辑任务：动态修改任务配置，支持展开/折叠动画
- 执行历史：查看最近 10 次执行记录，支持分页浏览
- 手动触发：随时手动触发一次任务执行
- 启用/禁用：灵活控制任务状态

**日志页面** - 任务历史查看
- 分页显示：每页最多 10 条记录
- 状态筛选：查看全部/运行中/已完成/失败任务
- 详细日志：展开查看完整的任务执行日志
- 任务删除：清理不需要的历史记录
- 最新优先：最新任务自动显示在顶部

**统计页面** - 数据概览
- 下载统计：总下载量、成功率、失败数
- 本月新增：当月新下载的本子数量
- 自动化统计：自动任务执行次数和状态
- 实时更新：数据自动刷新

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

## 常见问题

### Q1: pip 安装依赖很慢或失败

**原因：** 默认使用国外的 PyPI 源，网络可能不稳定

**解决方案一：更换 pip 镜像源（推荐）**
```bash
# 清华大学镜像源
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 或者使用阿里云镜像源
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 或者使用中科大镜像源
pip config set global.index-url https://mirrors.ustc.edu.cn/pypi/web/simple
```

**解决方案二：更换 Linux 系统软件源**

使用 [LinuxMirrors](https://github.com/SuperManito/LinuxMirrors) 一键更换系统软件源：
```bash
bash <(curl -sSL https://linuxmirrors.cn/main.sh)
```

支持 Debian、Ubuntu、CentOS、Fedora、Alpine、Arch 等主流发行版。

### Q2: 提示 "未安装 jmcomic 模块"

**解决：**
```bash
pip install jmcomic -U
```

### Q3: 下载失败或登录失败

**检查：**
1. 网络连接是否正常
2. 是否能访问禁漫网站（可能需要科学上网）
3. 账号密码是否正确（如果使用登录功能）

### Q4: 提示 "未找到 7z 命令"

**解决（仅导出收藏夹需要）：**
- Windows: 安装 [7-Zip](https://www.7-zip.org/)
- Linux: `sudo apt install p7zip-full`
- Mac: `brew install p7zip`

或者在配置中设置 `ENABLE_ZIP = False` 不使用压缩。

### Q5: 如何找到本子 ID？

在禁漫网站上，本子的 URL 格式为：
```
https://jmcomic.me/album/422866/
                     ^^^^^^
                    这就是ID
```

### Q6: 下载速度慢怎么办？

1. 使用 `api` 客户端（默认）
2. 检查网络连接
3. 可能需要科学上网

### Q7: 可以定时自动运行吗？

**可以！有以下方式：**

1. **使用 Web 界面的自动化功能**（推荐）
   - 启动 Web 服务器：`python web_server.py`
   - 在"自动化"页面创建定时任务
   - 支持 Cron 表达式，灵活设置运行时间

2. **系统任务计划**
   - **Windows**：使用"任务计划程序"定时运行 `python local_download.py`
   - **Linux/Mac**：使用 Cron
     ```bash
     crontab -e
     # 每天凌晨2点运行
     0 2 * * * cd /path/to/project && python local_download.py
     ```

3. **继续使用 GitHub Actions**
   - 如果需要云端自动化，查看原项目教程

---

## 对比：本地 vs GitHub Actions

| 特性 | 本地运行（本工具） | GitHub Actions |
|------|-------------------|----------------|
| **配置难度** | 简单 | 较复杂 |
| **运行方式** | 本地手动 | 云端自动 |
| **数据隐私** | 完全本地 | 上传到 GitHub |
| **定时任务** | 需自行配置 | 内置支持 |
| **网络要求** | 需能访问禁漫 | 无限制 |
| **立即执行** | 立即 | 需等待 |
| **存储限制** | 本地硬盘大小 | GitHub 限制 |

---

## 使用技巧

### 批量下载多个本子

在 `local_download.py` 中可以一次性配置多个本子 ID：

```python
ALBUM_IDS = """
422866
123456
789012
345678
901234
"""
```

### 只下载新章节

可以使用插件功能，参考原项目文档的"只下载新章插件"。

### 转换图片格式

如果需要统一图片格式，配置 `IMAGE_SUFFIX`：

```python
IMAGE_SUFFIX = ".png"  # 所有图片转为PNG
```

### 自定义下载目录

```python
# 绝对路径
DOWNLOAD_DIR = "D:/禁漫本子/"

# 相对路径
DOWNLOAD_DIR = "./my_comics/"
```

---

## 安全建议

1. **不要分享配置文件** - 如果其中包含账号密码
2. **定期修改密码** - 建议定期修改禁漫账号密码
3. **设置压缩密码** - 导出收藏夹时建议设置密码
4. **妥善保管数据** - 下载和导出的文件妥善保管

---

## 注意事项

1. **遵守法律法规** - 请遵守当地法律法规
2. **尊重版权** - 仅供个人学习研究使用
3. **减轻服务器压力** - 不要频繁大量下载
4. **网络要求** - 某些地区可能需要科学上网

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

### 插件系统

jmcomic 提供了强大的插件系统，支持：
- 登录插件
- 硬件监控插件
- 只下载新章插件
- 压缩文件插件
- PDF 合并插件
- 等等...

详见原项目文档。

---

## 获取帮助

1. **查看原项目文档**
   - 访问：https://jmcomic.readthedocs.io/

2. **提交 Issue**
   - 如果遇到 bug，到原项目提交 Issue
   - GitHub: https://github.com/hect0x7/JMComic-Crawler-Python/issues

3. **检查依赖安装**
   ```bash
   pip install -r requirements-web.txt
   ```

---

## 致谢

本工具基于 [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) 项目开发。

感谢原作者 **hect0x7** 提供的优秀框架！

---

## 更新日志

### v1.0.1 (2025-10-26) - 当前版本 ✨
- **UI 优化** - 全面优化用户界面体验
  - 添加网站图标 (favicon)
  - 优化动画效果，更流畅的展开/折叠动画
  - 改进卡片悬停效果，避免过度动画
- **分页功能** - 优化大量数据的浏览体验
  - 手动任务日志分页（每页 10 条）
  - 自动化任务执行历史分页（每页 10 条）
  - 自定义分页样式，蓝色箭头按钮，圆角矩形设计
- **数据持久化优化** - 精简存储
  - 手动任务只保留最近 10 条记录
  - 自动化任务执行历史每个任务保留 10 条
  - 自动清理旧数据，避免数据库膨胀
- **日志显示优化** - 更清晰的日志分类
  - 下载任务显示为"下载"
  - 导出任务显示为"导出"
  - 移除任务 ID 显示，界面更简洁
- **排序优化** - 最新记录置顶
  - 手动任务按创建时间倒序排列
  - 最新任务自动显示在顶部
- **项目清理** - 移除测试和调试文件
  - 删除所有测试脚本
  - 删除环境检查工具
  - 保留核心功能文件

### v1.0.0 (2025-10-25) - 初始版本 🚀
- **压缩功能** - 支持下载完成后自动压缩
  - 支持 ZIP 和 7z 两种格式
  - 支持整本/分章两种压缩级别
  - 支持密码加密和压缩后删除原文件
  - 手动下载和自动化任务都可配置
- **高级重试机制** - 智能域名选择策略
  - 自动记录域名失败次数
  - 优先使用成功率高的域名
  - 提高下载成功率和速度
- **默认目录规则优化** - 改为 `Aauthoroname/Pindextitle`
  - Aauthoroname：[作者]标题 格式
  - Pindextitle：第X話 标题 格式
  - 更清晰的文件组织结构

### v1.0.0-beta (2025-10-22~10-25) - 开发历程
- **Web 界面开发**
  - 现代化的 Web 管理界面
  - 任务管理、实时进度、日志查看
  - 优雅的 UI 设计，参考 miao-kit 风格
  - 实时刷新和自动更新
- **自动化功能**
  - 定时同步收藏夹
  - 自动下载新本子（跳过已有）
  - Cron 表达式灵活调度
  - 任务编辑和配置修改
  - 并发控制（1-10）
- **Rust 高性能下载器集成**
  - CPU/内存占用降低 70-90%
  - 下载速度提升 2-3 倍
  - 异步并发，支持 100+ 并发
  - 智能重试和自动降级
- **UI/UX 优化**
  - 自定义提示框
  - 图标按钮
  - 统计面板（成功率、本月新增）
  - 卡片内容对齐优化
- **命令行工具**
  - 本地下载本子功能
  - 本地导出收藏夹功能
  - 交互式配置

---

## 许可证

本工具基于原项目开发，遵循原项目的许可证。

---

**祝你使用愉快！**

如有任何问题，请查阅原项目文档或提交 Issue。

---

*最后更新: 2025-10-26*

