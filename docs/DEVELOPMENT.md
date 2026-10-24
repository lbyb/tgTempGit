# 开发与调试记录

本文记录这次实现的实际过程、遇到的问题和验证方式，便于判断实现是否符合预期，
也方便后续维护。

## 1. 需求拆解

原始需求里有两个容易产生歧义的词：

- “书签”通常指 PDF 大纲（outline / bookmark）；
- “打上标签”“正文从第 1 页开始累积”又很像 PDF 页码标签（page labels）。

为了避免只实现其中一种导致使用效果不符合预期，最终同时写入了：

1. **大纲书签**：`目录`、`目录 1…k`、`正文`、`第1页…第N页`；
2. **页码标签**：目录页显示 `目录 1…k`，正文页显示 `1…N`。

正文编号只看用户给出的“正文第 1 页”物理页码，不猜测封面、前言或印刷页码。
默认同时启用两者；命令行可用 `--no-page-labels` 只写书签。

两个输入的约束：`1 <= 目录页 < 正文第1页 <= 总页数`。目录页到正文前一页都算目录，
正文第 1 页到 PDF 最后一页都算正文。

## 2. 隔离环境

要求不污染本地环境，因此所有 Python 依赖都安装在项目内虚拟环境，测试 PDF 全部
写到 pytest 的临时目录，不修改仓库外的文件。

```bash
cd /root/pupdf
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install 'PyMuPDF==1.24.14' 'pytest==8.3.3'
.venv/bin/pip install -e .
```

实际环境：

```text
Ubuntu 24.04
Python 3.12.3
PyMuPDF 1.24.14 (MuPDF 1.24.11)
pytest 8.3.3
```

`.venv/`、`.scratch/`、构建缓存都放进了 `.gitignore`。

## 3. 先验证 PyMuPDF 行为

正式写代码前先做了两个小实验。

### 3.1 页码标签中文编码

最初直接调用：

```python
doc.set_page_labels([
    {"startpage": 2, "prefix": "目录 ", "style": "D", "firstpagenum": 1},
])
```

保存后检查 PDF 目录对象，发现 `/P` 里是 UTF-8 原始字节：

```text
/P<E79BAEE5BD9520>
```

PDF 规范中的文本字符串应是 PDFDocEncoding 或带 BOM 的 UTF-16BE；无 BOM 的 UTF-8
在部分阅读器中会显示为乱码。于是改为把 `目录 ` 编码为 `FEFF76EE5F550020`
（UTF-16BE + BOM），再用 PDF 八进制转义交给 `set_page_labels`：

```python
payload = b"\xfe\xff" + text.encode("utf-16-be")
escaped = "".join(f"\\{b:03o}" for b in payload)
```

最终 PDF 中的对象是：

```text
/PageLabels <</Nums[2<</P<FEFF76EE5F550020>/S/D>>4<</S/D>>]>>
```

这是标准写法，Acrobat、MuPDF、Chrome PDF 阅读器等可以正确解析。注意
PyMuPDF 自带的 `Page.get_label()` 对十六进制 `/P` 会原样返回
`<FEFF...>`，这是 PyMuPDF 辅助函数的限制，不代表 PDF 写错；测试因此同时检查
原始 xref。

### 3.2 原子覆盖

不能直接 `doc.save(原路径)`。最终流程：

1. 打开并校验原 PDF（拒绝加密、损坏、零页）；
2. 修改内存中的书签和页码标签；
3. 在**同目录**创建 `.pupdf-*.pdf` 隐藏临时文件；
4. 保存临时文件，关闭原文档；
5. 重新打开临时 PDF，校验页数和书签数量；
6. 可选创建 `.bak`；
7. `os.replace(temp, original)` 原子替换；
8. 失败时删除临时文件，原文件不动。

## 4. 测试与真实排错

测试使用 PyMuPDF 现场生成小 PDF，不依赖仓库里的二进制样本。

### 4.1 第一次完整测试

```bash
.venv/bin/pytest -q
```

结果：

```text
47 passed, 3 failed, 1 skipped
```

三个失败都提供了有效信息：

1. **关闭页码标签后测试断言 `get_label()` 等于 `"3"` 失败**
   - 原因：没有 `/PageLabels` 时 PyMuPDF 的 `get_label()` 返回空字符串，而不是
     阅读器默认编号。
   - 处理：改为断言 PDF 目录中不存在 `/PageLabels`，这更准确地验证了“未写入”。

2. **只设置 owner password 的 PDF 没有被识别为加密**
   - 原因：MuPDF 对这种 PDF 的 `needs_pass`、`is_encrypted` 都是假，但重写会
     丢失原有加密/权限。
   - 处理：增加检查 `metadata["encryption"]`，此类 PDF 也拒绝处理，并在 README
     中说明。

3. **模拟写入失败时残留 `.pupdf-*.pdf` 临时文件**
   - 原因：保存失败发生在清理用的 `try/finally` 之外。
   - 处理：把保存、校验、替换合并到同一个清理作用域，并用测试固定这一行为。

修复后（后续又补充了临时目录不可写、交互页码边界等测试）：

```text
53 passed, 1 skipped
```

跳过的是 GUI 冒烟测试，因为宿主机 Python 没有 Tkinter。GUI 在隔离的 Ubuntu
容器 + Xvfb 中单独验证。

### 4.2 GUI 验证

宿主机是无桌面的 Linux，直接 `apt install python3-tk` 会污染系统环境，所以使用
一次性 Docker 容器。容器内安装 `python3-tk`、`xvfb` 和中文字体，依赖安装到容器的
`/tmp` 虚拟环境（不写入宿主机环境），然后运行：

```bash
Xvfb :99 -screen 0 1280x900x24 &
DISPLAY=:99 python -m pytest -q tests/test_gui_smoke.py
```

验证内容：

- 通过 `initial_pdf` 预加载 PDF；
- 输入两个页码后预览文案正确；
- 同步执行（测试专用开关）后文件确实被覆盖、书签和页码标签可读；
- 非法页码弹错且不写文件；
- 空目录启动提示正确。

单独运行 GUI 测试：

```text
...                                                                      [100%]
3 passed in 0.47s
```

在同一次容器环境中运行完整测试（含 GUI）：

```text
.......................................................                  [100%]
56 passed in 5.11s
```

界面截图保存在 [截图](screenshot.png)，也在 README 中展示。

### 4.3 用 pikepdf/qpdf 做独立结构校验

PyMuPDF 读取自己写出的文件可能掩盖编码问题，因此又用独立的 qpdf 绑定验证：

```python
with pikepdf.open("output.pdf") as pdf:
    print(pdf.check_pdf_syntax())      # []
    print(pdf.Root.PageLabels.Nums)    # /P 为 “目录 ”
    print(pdf.open_outline().root)     # 目录/正文及子书签
```

实际输出：

```text
syntax check: []
PageLabels Nums: [2, {"/P": "目录 ", "/S": "/D"}, 4, {"/S": "/D"}]
top-level: [('目录', ['目录 1', '目录 2']),
            ('正文', ['第1页', ..., '第8页'])]
```

这说明页码标签中的中文被独立解析器识别为“目录 ”，不是乱码。

### 4.4 代码质量检查

```bash
.venv/bin/python -m compileall -q src tests packaging/windows_launcher.py
.venv/bin/pip install ruff
.venv/bin/ruff check src tests packaging/windows_launcher.py
.venv/bin/ruff format --check src tests packaging/windows_launcher.py
```

最终结果：

```text
All checks passed!
14 files already formatted
```

## 5. CLI 手工验收

```bash
cp sample.pdf /tmp/demo.pdf
pupdf --pdf /tmp/demo.pdf --toc-page 5 --body-page 7 --dry-run
pupdf --pdf /tmp/demo.pdf --toc-page 5 --body-page 7
```

验收点：

- dry-run 不修改 SHA-256；
- 覆盖后 PDF 仍可打开，页数不变；
- 大纲数量和页码正确；
- 目录页/正文页页码标签正确；
- 多 PDF 目录拒绝自动选择；
- 非法页码退出码为 2，文件错误退出码为 1；
- 交互模式输入 `目录页`、`正文第1页` 两次后正常执行。

调试中还修复了一个交互边界：在 8 页 PDF 上只给 `--toc-page 8` 时，旧逻辑会
用 `9..8` 这种不可能区间反复提示正文页码。现在会在提示前直接报错退出。

## 6. Windows 打包

PyInstaller 不能从 Linux 交叉编译 Windows PE，因此提供：

- `packaging/windows_launcher.py`：无控制台入口，启动失败时用 Win32 MessageBox
  显示错误并写日志；
- `pupdf.spec`：单文件、`console=False`、收集 PyMuPDF 二进制；
- `scripts/build_windows.bat`：在 Windows 上创建 `.venv-build`、装依赖、跑测试、
  构建 `dist\Pupdf.exe`；
- `.github/workflows/windows-build.yml`：Windows CI 构建并上传 artifact。

拖放行为不依赖第三方 DND 库：Windows 把拖到 exe 上的文件作为 `sys.argv[1]`
传入，程序读取该参数并在 GUI 中预填 PDF 路径，但仍让用户输入两个页码。

为了提前验证 spec 和单文件打包逻辑，在 Linux 容器中同样执行了
`python -m PyInstaller --noconfirm --clean pupdf.spec`。产物约 40 MB，放在
只含一个 PDF 的目录中启动后，Xvfb 截屏确认：程序成功自动发现该 PDF、加载
Tk 界面并显示页数。这个测试不能替代 Windows 构建，但验证了 spec 的入口、
PyMuPDF 收集和 one-file 结构。

## 7. 复现命令汇总

```bash
# Linux 开发/测试
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q

# Linux 运行
pupdf
pupdf --toc-page 5 --body-page 7
pupdf --gui

# Windows 构建
scripts\build_windows.bat
```

## 8. 后续修改建议

- 想改书签层级/命名：`src/pupdf/core.py` 的 `ProcessPlan.generated_outline`；
- 想改目录页标签：`ProcessPlan.page_labels` 与 `TOC_PREFIX`；
- 想增加“保留原书签”GUI 复选框：给 `ProcessPdf` 调用传入
  `keep_outline=True`，并在 `gui_app.py` 增加 Tk 变量；
- 想支持加密 PDF：需要让用户输入密码，并决定输出是否继续加密；
- 想解析目录页文字自动识别章节：应新增独立解析模块，不要改动原子写入流程；
- 想批量处理目录下多个 PDF：在 `discovery.find_pdfs` 之上增加循环，并明确
  覆盖/备份策略。
