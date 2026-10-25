# Pupdf - 单文件 PDF 逐页书签工具

一个跨平台的 Python 脚本：给 PDF 创建“目录 + 正文页码”书签和页码标签，
处理后**直接覆盖原 PDF**。不再包含 Windows 图形界面或 exe，Linux、macOS、
Windows 共用同一个脚本。

只要求输入两个页码：

1. 目录页所在页；
2. 正文第 1 页所在页。

推荐用 [uv](https://docs.astral.sh/uv/) 直接运行。脚本已经用 PEP 723 声明了
Python 版本和 PyMuPDF 依赖，uv 会自动准备隔离环境，**不会安装到系统 Python
或全局 site-packages**。

## 功能

- 自动查找当前目录（或 `--dir` 指定目录）中的唯一 PDF。
- 根据两个页码自动推算：
  - 目录页范围：`目录页` 到 `正文第1页 - 1`；
  - 正文页范围：`正文第1页` 到最后一页，并从 1 开始编号。
- 写入**平铺** PDF 大纲书签，不再分两级：
  - 目录只生成一个“目录”书签，指向目录首页；
  - 正文每一页生成一个一级书签，书签名直接是阿拉伯数字 `1`、`2`…`N`；
  - 不生成“目录 1”“第1页”“正文”等冗余层级和描述。
- 写入规范化页码标签：
  - 目录前的前置页（封面、前言等）默认使用 `A`、`B`、`C`…；如果原标签明确
    使用罗马数字，则规范为 `i`、`ii`、`iii`…；
  - 目录页使用罗马数字 `i`、`ii`…；
  - 正文及之后使用阿拉伯数字 `1`、`2`…`N`，不补零。
- 使用隐藏临时文件 + 重新打开校验 + 原子替换，失败时原 PDF 不受影响。
- 默认替换原有书签；可选保留原书签并追加。默认不生成 `.bak`，可按需开启。
- 只依赖 PyMuPDF，Windows / Linux / macOS 使用同一套代码。

### 书签示例

假设 PDF 共 100 页：

| 输入 | 值 |
| --- | --- |
| 目录页所在页码 | 5 |
| 正文第 1 页所在页码 | 7 |

生成结果：

```text
目录                 -> PDF 第 5 页

1                    -> PDF 第 7 页
2                    -> PDF 第 8 页
...
94                   -> PDF 第 100 页
```

同时写入页码标签（假设 PDF 第 1-4 页是封面/前言）：

```text
PDF 第 1-4 页     -> A、B、C、D
PDF 第 5-6 页     -> i、ii
PDF 第 7-100 页   -> 1、2、3 … 94
```

如果原有前置页标签明确是罗马数字（例如 style 为 `r`/`R`，或 prefix 是
`i`、`ii` 等），则会规范为连续的罗马数字，而不是改成 A/B/C。

> “目录页”和“正文第 1 页”都按 PDF 阅读器中的**物理页序号**填写，从 1 开始。
> 正文前的页面仍然会保留在 PDF 中，只是统一规范页码标签，不生成正文书签。

## 安装 uv

只需要安装 uv，不需要手动安装 Python 或 PyMuPDF。

**Windows（PowerShell）**

```powershell
winget install --id=astral-sh.uv -e
# 或者：
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Linux / macOS**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后确认：

```bash
uv --version
```

## 直接运行

### 交互模式（最常用）

把唯一一个 PDF 放在当前目录，然后运行脚本：

```bash
cd /path/to/book-folder
uv run /path/to/pupdf.py
```

Windows PowerShell：

```powershell
cd D:\books
uv run C:\tools\pupdf.py
```

也可以先把 `pupdf.py` 复制到 PDF 所在目录：

```powershell
cd D:\books
uv run .\pupdf.py
```

程序会提示：

```text
目录页所在页码（1-99）：
正文第1页所在页码（6-100）：
```

输入两个页码后，直接覆盖该 PDF。

第一次运行时 uv 会下载 Python（如果需要）和 PyMuPDF；之后使用缓存，不会在
系统 Python 中安装任何包。需要清理 uv 缓存时执行 `uv cache clean`。

如果当前目录本身是另一个 uv/Python 项目，可加 `--no-project`，明确只使用脚本
自己的依赖：

```bash
uv run --no-project pupdf.py
```

### 非交互模式

```bash
# 自动查找当前目录的唯一 PDF
uv run pupdf.py --toc-page 5 --body-page 7

# 指定 PDF
uv run pupdf.py --pdf /data/books/demo.pdf --toc-page 5 --body-page 7

# 指定查找目录
uv run pupdf.py --dir /data/books --toc-page 5 --body-page 7

# 先预览，不修改文件
uv run pupdf.py --toc-page 5 --body-page 7 --dry-run

# 保留原书签并追加；覆盖前生成 demo.pdf.bak
uv run pupdf.py --toc-page 5 --body-page 7 --keep-outline --backup

# 只写书签，不写页码标签
uv run pupdf.py --toc-page 5 --body-page 7 --no-page-labels
```

Windows 路径带空格时加引号：

```powershell
uv run C:\tools\pupdf.py --pdf "D:\My Books\demo.pdf" --toc-page 5 --body-page 7
```

### 命令行参数

```text
--pdf PATH            指定 PDF（默认自动查找唯一 PDF）
--dir DIR             自动查找 PDF 的目录（默认当前目录）
--toc-page N          目录页所在页码
--body-page N         正文第 1 页所在页码
--keep-outline        保留并追加原书签（默认替换）
--no-page-labels      不写入页码标签
--backup              覆盖前创建 <原名>.pdf.bak
--dry-run             只显示计划，不修改
--debug               未预期错误时打印完整 traceback
--version             显示版本
```

退出码：`0` 成功；`1` PDF/文件错误；`2` 输入或参数错误；`130` 用户取消。

## 脚本声明的运行环境

`pupdf.py` 顶部的 PEP 723 元数据：

```python
# requires-python = ">=3.10,<3.14"
# dependencies = ["pymupdf==1.24.14"]
```

uv 会按这个声明创建临时运行环境。Windows 上不需要提前安装 Python；如果本机
没有合适版本，uv 可以自动下载受管理的 Python 3.12/3.13。PyMuPDF 使用官方
Windows wheel，不涉及编译工具。

如果不想使用 uv，也可以手动运行（会安装到当前 Python 环境）：

```bash
python -m pip install -r requirements.txt
python pupdf.py --toc-page 5 --body-page 7
```

不推荐在 Windows 全局 Python 中这样做；优先使用 uv。

## 行为与安全说明

- **覆盖目标**：始终覆盖打开的那个 PDF，不会另存新文件。可用 `--backup`，
  或先自行复制原文件。
- **原子写入**：先写同目录隐藏临时文件，重新打开并校验页数/书签数量，再用
  `os.replace` 替换原文件。任何一步报错都会删除临时文件，原文件保持不变。
- **文件锁**：Windows 阅读器打开 PDF 时可能锁定文件。覆盖失败时请关闭阅读器
  再重试。
- **加密 PDF**：带用户密码或权限密码的 PDF 会拒绝处理，避免在重写时丢失加密
  或权限设置。
- **数字签名**：任何 PDF 修改都会使已有数字签名失效。
- **原书签**：默认替换。需要保留时用 `--keep-outline`；保留模式会保留标题、
  层级和页目标，但无法保留指向外部 URL 的书签。
- **页码标签**：每页写入显式 prefix（A/B/i/1…），不依赖自动编号，不保留
  `01`、`001` 这类前导零；即使阅读器不显示页码标签，大纲书签仍然有效。
- **自动查找**：只查一层目录，不递归；忽略本工具自己的 `.pupdf-*.pdf` 临时文件。
- **大文件**：处理需要重写整个 PDF，页数很多时需要一些时间。

## 项目结构

```text
pupdf.py          单文件程序：PDF 引擎 + CLI + PEP 723 依赖声明
tests/            核心、CLI、文件查找测试
pytest.ini        测试配置
ruff.toml         代码检查配置
requirements.txt  不使用 uv 时的 PyMuPDF 依赖
docs/DEVELOPMENT.md  本次实现和调试过程
.github/workflows/tests.yml  Linux + Windows CI
```

## 二次开发接口

脚本也可以作为模块导入：

```python
from pupdf import analyze_pdf, build_plan, execute_plan, process_pdf

info = analyze_pdf("book.pdf")
print(info.total_pages, info.has_outline)

# 一步完成（会覆盖原文件）
result = process_pdf("book.pdf", toc_page=5, body_page=7, backup=True)
print(result.generated_bookmarks)

# 或者先规划、预览，再执行
plan = build_plan("book.pdf", toc_page=5, body_page=7, keep_outline=True)
print(plan.generated_outline)
result = execute_plan(plan, backup=False)
```

主要数据类：

- `PageLayout`：已校验的 1-based 页码布局，提供 `toc_pages`、`body_pages`。
- `PdfInfo`：页数、标题、是否已有大纲。
- `ProcessPlan`：不可变的处理计划，包含平铺的 `final_outline`、前置页标签类型
  `front_label_kinds` 和每页 `page_labels`。
- `ProcessResult`：实际写入结果。

要调整书签命名，修改 `ProcessPlan.generated_outline`；要调整页码标签规则，
修改 `_page_labels_for_layout`（以及前置页识别函数 `_classify_front_label`）。
异常统一继承 `PupdfError`。

## 测试

不需要创建项目虚拟环境，uv 会临时准备测试依赖：

```bash
uv run --with pytest --with pymupdf==1.24.14 pytest -q
```

代码检查：

```bash
uvx ruff check pupdf.py tests
uvx ruff format --check pupdf.py tests
```

测试覆盖：

- 平铺书签、目录首页、正文 1…N、无“第N页/目录N”描述、原书签替换/保留、幂等性；
- 前置页字母/罗马数字规范化、目录罗马数字、正文去前导零、关闭页码标签；
- 非法页码、加密 PDF、损坏 PDF、扩展名错误；
- 覆盖失败/写入失败/临时目录不可写时原文件不变、临时文件被清理；
- 自动查找唯一/多个 PDF、默认当前目录；
- CLI 参数、交互输入、dry-run、`--dir`、退出码。

GitHub Actions 在 **Ubuntu 和 Windows** 两个平台执行同一套测试，并额外运行
`uv run pupdf.py --version` 验证 Windows 下的 uv 启动链路。

## 常见问题

**`uv: command not found`**

先按上面的 Windows PowerShell 或 Linux 命令安装 uv，然后重新打开终端。

**提示“目录中有多个 PDF 文件”**

自动模式只处理唯一 PDF。只保留一个，或用 `--pdf` 指定文件。

**提示“正文第1页必须大于目录页”**

两个输入之间至少要有一页目录。请确认输入的是 PDF 物理页码，不是印刷页码。

**覆盖失败，提示文件被占用**

关闭 Adobe Acrobat、Edge、SumatraPDF 等正在打开该文件的程序，并检查文件是否
只读。失败不会损坏原文件；重新运行即可。

**Windows 终端中文显示异常**

建议使用 Windows Terminal / PowerShell 7；脚本会把重定向输出设置为 UTF-8。
老式 `cmd.exe` 可先执行 `chcp 65001`。

## 已知限制

- 不处理带密码的 PDF。
- 不解析目录页上的文字来确定章节，只根据用户给出的两个页码生成逐页书签。
- 目录前的前置页如果没有可用标签信息，默认按 A/B/C 编号；需要其他规则时可修改
  `_classify_front_label` 和 `_page_labels_for_layout`。
- 重写 PDF 可能改变文件内部结构，不适合需要保留数字签名或严格 PDF/A 认证的文件。
- 自动查找只针对指定目录，不扫描子目录。
- 不提供 GUI 或预编译 exe；需要 Python 脚本运行环境（uv 会简化这一步）。

## License

MIT，见 [LICENSE](LICENSE)。
