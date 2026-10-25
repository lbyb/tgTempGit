# 开发与调试记录

本文记录本次简化和实际验证过程，便于判断实现是否符合预期，也方便后续维护。

## 1. 需求调整

根据最新要求，放弃 Windows GUI / exe，改为单文件 Python 脚本，并优先支持：

- Linux、macOS、Windows 共用同一份代码；
- 用 `uv run pupdf.py` 直接运行；
- uv 自动读取脚本内声明的依赖，不向系统 Python 安装包；
- CLI 只要求输入两个页码；
- 继续保留原有的 PDF 书签、页码标签和原子覆盖能力。

因此删除了：

- Tkinter 界面 `gui.py` / `gui_app.py`；
- Windows PyInstaller 配置和构建脚本；
- 拖放参数解析、截图和 Windows 专用 CI；
- 旧的 `src/` 包结构、`pyproject.toml` 和 `requirements-dev.txt`。

新的核心入口只有一个文件：[`pupdf.py`](../pupdf.py)。

随后根据“书签去层级、去描述、prefix 规范化”的要求，又调整了输出：

- 大纲改为平铺：一个 `目录` + 正文 `1…N`；
- 去掉 `第N页`、`目录 N`、`正文` 等文字；
- 页面标签按前置页字母/罗马、目录罗马、正文阿拉伯数字生成；
- 正文不再补零，`1` 不会写成 `01`/`001`。

具体规则见第 3 节。

## 2. 单文件结构

脚本顶部使用 PEP 723 声明运行环境：

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "pymupdf==1.24.14",
# ]
# ///
```

`uv run pupdf.py` 会据此创建隔离运行环境。Windows 上不需要预装 Python；
uv 可以下载受管理的 Python，PyMuPDF 使用官方 Windows wheel。

文件内部按层组织：

1. `PupdfError` 及子类：统一用户错误；
2. `find_pdfs` / `find_single_pdf`：单 PDF 发现；
3. `PageLayout` / `ProcessPlan`：页码校验和处理计划；
4. `build_plan` / `execute_plan` / `process_pdf`：PDF 处理稳定 API；
5. CLI 解析、交互提示、计划打印和退出码；
6. `__all__`：显式公开可复用接口。

## 3. 书签与页码标签规范

最新版本按以下规则输出：

- 大纲完全平铺，不再有二级书签：
  - 只生成一个 `目录` 书签，指向目录范围的首页；
  - 正文每一页一个一级书签，标题直接是 `1`、`2`…`N`；
  - 不生成 `目录 1`、`第1页`、`正文` 之类的层级或描述。
- 页码标签全部改为每页显式 prefix，不使用自动编号拼接：
  - 目录前的前置页：默认 `A`、`B`、`C`…；如果原标签的 style 是罗马数字，
    或 prefix 明确是 `i`、`ii`、`!` 等罗马形式，则改为 `i`、`ii`…；
  - 目录页：罗马数字 `i`、`ii`…；
  - 正文及之后：阿拉伯数字 `1`、`2`…`N`，不补零；
  - 保留 `.pdg` 清理和 category（`cov`/`bok`/`leg`/`fow`）识别。
- 前置页标签类型由 `_front_label_kinds` 读取原 PDF 得到：
  - 优先看 PDF page-label 的 `style`（`r`/`R`/`A`/`a`）；
  - style 为空时看 prefix 开头的字母/罗马记号；
  - `cov/bok/leg/fow` 按前置页字母处理；
  - 无法判断时默认按字母处理。
- 页码标签由 `_page_labels_for_layout` 生成：
  - 字母计数与正文数字独立；
  - 目录页的罗马计数始终从 i 开始；
  - 每页生成 `{'startpage': i, 'prefix': ..., 'style': '', 'firstpagenum': 1}`，
    避免旧 style 继续自动拼接数字。
- 写入流程：内存修改 → 同目录隐藏临时文件 → 关闭原文档 → 重新打开校验
  → 可选 `.bak` → `os.replace` 原子覆盖；
- 保存/校验/替换任意一步报错，都会删除临时文件，原 PDF 不变；
- 加密 PDF、损坏 PDF、非法页码、被锁定的 PDF 都有明确中文提示。

## 4. 跨平台处理

为了让 Windows 也能直接使用：

- 不使用 `fcntl`、`os.fork`、shell 脚本或 Tkinter；
- 文件操作全部使用 `pathlib`；
- 原子替换使用 Windows 也支持的 `os.replace`；
- `fsync` 只在 POSIX 下执行，Windows 自动跳过；
- 路径带空格、中文、盘符均由 Python `Path` 处理；
- 启动时把 stdout/stderr 重定向编码设为 UTF-8，避免英文 Windows 管道输出
  中文时报编码错误；
- 交互输入使用标准 `input()`，Windows PowerShell / Windows Terminal 可用；
- GitHub Actions 矩阵覆盖 `ubuntu-latest` 和 `windows-latest`，两边运行同一套
  测试，并额外执行 `uv run pupdf.py --version`。

Windows 的 CI 配置在 [`.github/workflows/tests.yml`](../.github/workflows/tests.yml)。
当前开发机是 Linux，因此没有在本机执行 Windows 原生测试；Windows job 会在
推送/PR 时执行。

## 5. 测试适配

旧测试导入的是 `pupdf.core`、`pupdf.discovery`，现在统一改为：

```python
import pupdf as core
from pupdf import analyze_pdf, ...
```

由于单文件就叫 `pupdf.py`，测试只要把仓库根目录加入 `sys.path`，`import pupdf`
就会加载脚本，不需要安装项目。

CLI 测试也从：

```text
python -m pupdf
```

改为：

```text
python /path/to/pupdf.py
```

并保留了 Windows 下的 UTF-8 环境变量和显式解码参数。

删除的测试：

- Tkinter GUI 冒烟测试；
- Windows 拖放参数解析测试；
- PyInstaller / exe 相关测试。

新增/保留的测试：

- 平铺书签、目录只出现一次、正文书签为 `1…N`；
- 前置页 A/B/C 与罗马数字识别；
- 目录页罗马数字、正文阿拉伯数字、无前导零；
- `--dir` 查找、默认当前目录查找；
- 单文件脚本的 `--version`、交互提示和退出码；
- 原书签替换/保留、原子覆盖、加密/损坏 PDF 等回归测试。

## 6. 实际验证

环境：

```text
uv 0.8.13
Python 3.12
PyMuPDF 1.24.14
```

### 6.1 uv 直接运行

```text
$ uv run pupdf.py --version
pupdf.py 0.3.0
```

首次运行会下载/安装 PyMuPDF 到 uv 管理的隔离环境；系统 Python 没有变化。
另外用 `uv run --python 3.10/3.13 pupdf.py --version` 验证了脚本声明的版本
下界和上界，PyMuPDF wheel 均可正常加载。

### 6.2 完整测试

为了让 sandbox 中的 uv 缓存落在工作区，测试时设置了：

```bash
export UV_CACHE_DIR=/root/pupdf/.uv-cache
export UV_PYTHON_INSTALL_DIR=/root/pupdf/.uv-python
uv run --with pytest --with pymupdf==1.24.14 pytest -q
```

结果（Python 3.12）：

```text
..........................................................               [100%]
59 passed
```

Python 3.13 也通过了同一套测试：

```text
59 passed in 4.24s
```

### 6.3 端到端 PDF 验证

在只含一个 PDF 的目录中：

```bash
uv run /root/pupdf/pupdf.py --toc-page 2 --body-page 4 --dry-run
uv run /root/pupdf/pupdf.py --toc-page 2 --body-page 4
```

实际输出摘要：

```text
PDF      ：/tmp/pupdf-label-demo/demo.pdf
总页数   ：12
目录页   ：第 3-4 页（2 页）
正文     ：第 5-12 页（8 页，书签“1”…“8”）
新增书签 ：9 条（1 条“目录” + 8 条正文页码）

完成：已覆盖 /tmp/pupdf-label-demo/demo.pdf
写入 9 条新书签，当前共 9 条书签。
```

重新打开 PDF 检查：

```text
labels:
1 {'startpage': 0, 'prefix': 'A'} display='A'
2 {'startpage': 1, 'prefix': 'B'} display='B'
3 {'startpage': 2, 'prefix': 'i'} display='i'
4 {'startpage': 3, 'prefix': 'ii'} display='ii'
5 {'startpage': 4, 'prefix': '1'} display='1'
...
12 {'startpage': 11, 'prefix': '8'} display='8'

toc: [[1, '目录', 3],
      [1, '1', 5], [1, '2', 6], ..., [1, '8', 12]]
```

说明书签已平铺、正文标题无“第/页”、页码没有前导零。

另外用独立的 qpdf 绑定 pikepdf 做结构校验：

```text
syntax: []
labels: [0 {P: A}, 1 {P: B}, 2 {P: i}, 3 {P: ii}, 4 {P: 1}, ...]
outline: [('目录', 0), ('1', 0), ('2', 0), ..., ('8', 0)]
```

说明 PDF 语法正常，`/PageLabels` 是 `A`/`B`/`i`/`ii`/`1` 这类显式前缀，
大纲是平铺结构。

### 6.4 代码检查

```bash
uvx ruff check pupdf.py tests
uvx ruff format --check pupdf.py tests
```

结果：

```text
All checks passed!
5 files already formatted
```

## 7. 复现命令汇总

```bash
# 直接运行（任意平台）
uv run pupdf.py

# 非交互
uv run pupdf.py --toc-page 5 --body-page 7
uv run pupdf.py --pdf /path/to/book.pdf --toc-page 5 --body-page 7

# 测试
uv run --with pytest --with pymupdf==1.24.14 pytest -q

# 代码检查
uvx ruff check pupdf.py tests
uvx ruff format --check pupdf.py tests
```

## 8. 后续修改建议

- 改书签命名/层级：`ProcessPlan.generated_outline`；
- 改页码标签：`_page_labels_for_layout` 和 `_classify_front_label`；
- 改 PDF 发现规则：`find_pdfs`；
- 改交互提示：`_read_page_numbers` / `_prompt_int`；
- 增加批量处理：遍历 `find_pdfs` 结果，但必须明确备份和覆盖策略；
- 增加其他输出格式：扩展 `ProcessResult`，不要绕开原子覆盖流程。

## 9. 已知限制

- 不处理带密码的 PDF；
- 重写 PDF 会使数字签名失效，也不保证严格 PDF/A；
- 不解析目录文字，只按两个页码生成逐页书签；
- 不提供 GUI 或 exe，需要 Python 脚本运行环境；
- Windows 真机测试依赖 GitHub Actions 或用户本机执行。
