import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, Callable
from urllib.parse import urlencode
from bs4 import BeautifulSoup

from backend.config import MAX_RETRIES, RETRY_DELAY, UA

# ---------------------------------------------------------------------------
# Playwright 浏览器单例管理
#
# annas-archive 自迁移到 DDoS-Guard 后，对 /search 等路径启用 JS 挑战
# （WebSocket + 浏览器指纹），纯 HTTP 客户端（httpx/requests）无法通过，
# 会收到 302 -> ?check=1 -> 403。只有真实浏览器执行挑战后才能拿到结果，
# 且挑战 cookie 绑定浏览器会话，无法提取后复用于 httpx。
#
# 因此这里维护一个全局无头 Chromium 实例，第一次访问时自动完成挑战，
# 之后同一会话内的请求直接复用已通过的 cookie。
#
# 重要：Playwright 的 sync API 绑定创建它的线程（greenlet），跨线程访问
# 会抛 "Cannot switch to a different thread"。FastAPI 请求与后台 series
# 任务运行在不同线程，因此所有浏览器操作必须提交到专用的单线程执行器，
# 确保浏览器始终在同一个线程中创建与访问。
# ---------------------------------------------------------------------------

_pw_lock = threading.RLock()
_pw_executor: ThreadPoolExecutor | None = None
_pw_playwright = None
_pw_browser = None
_pw_context = None
_pw_warmed_origins: set[str] = set()

PW_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
]


def _get_executor() -> ThreadPoolExecutor:
    """获取专用的单线程浏览器执行器。"""
    global _pw_executor
    with _pw_lock:
        if _pw_executor is None:
            _pw_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="aa-browser",
            )
        return _pw_executor


def _ensure_browser():  # type: ignore[no-untyped-def]
    """惰性启动全局无头浏览器，返回共享的 BrowserContext。

    必须在专用浏览器线程内调用。
    """
    global _pw_playwright, _pw_browser, _pw_context
    if _pw_browser is not None:
        return _pw_context
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("缺少 playwright 依赖，请安装：pip install playwright && playwright install chromium") from e

    _pw_playwright = sync_playwright().start()
    _pw_browser = _pw_playwright.chromium.launch(
        headless=True,
        args=PW_ARGS,
    )
    _pw_context = _pw_browser.new_context(
        user_agent=UA,
        viewport={"width": 1366, "height": 768},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    return _pw_context  # type: ignore[return-value]


def _warmup_sync(origin: str) -> None:
    """在浏览器线程内访问镜像根路径，让 DDoS-Guard 挑战自动解决。

    记录已 warmup 的域名，域名变化时对新域名重新 warmup，
    避免 login 端点返回的 TLD 变化导致新域名挑战失败。
    """
    global _pw_warmed_origins
    if origin in _pw_warmed_origins:
        return
    try:
        ctx = _ensure_browser()
        page = ctx.new_page()
        try:
            page.goto(origin + "/", wait_until="domcontentloaded", timeout=60000)
            for _ in range(20):
                if "DDoS" not in page.title():
                    break
                time.sleep(1)
            _pw_warmed_origins.add(origin)
        finally:
            page.close()
    except Exception as e:
        print(f"[WARN] AA warmup 失败: {e}")


def _warmup(origin: str) -> None:
    """将 warmup 任务提交到浏览器专用线程执行（线程安全）。"""
    _get_executor().submit(_warmup_sync, origin).result(timeout=120)


def _fetch_one_sync(q: str, origin: str, base_url: str) -> Tuple[Optional[BeautifulSoup], str, Optional[BeautifulSoup]]:
    """在浏览器线程内执行单个 ISBN 的搜索抓取。"""
    params = {
        "index": "",
        "page": "1",
        "q": q,
        "display": "table",
        "ext": "pdf",
        "acc": "aa_download",
        "src": ["zlibzh", "duxiu"],
        "sort": "",
    }

    soup: Optional[BeautifulSoup] = None
    ctx = _ensure_browser()
    _warmup_sync(origin)
    url = base_url + "?" + urlencode(params, doseq=True)

    for attempt in range(1, MAX_RETRIES + 1):
        page = None
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # 等待 DDoS-Guard 挑战自动解决：轮询 DOM 中结果容器出现。
            # 期间页面可能多次 reload/导航，title 也会在 DDoS-Guard 与
            # 正常标题间切换，因此以 DOM 是否出现结果容器为准。
            found = False
            for _ in range(40):
                time.sleep(1)
                try:
                    if page.locator(".js-aarecord-list-outer").count() > 0:
                        found = True
                        break
                except Exception:
                    pass
            if not found:
                print(f"[WARN] 等待结果容器超时，第 {attempt}/{MAX_RETRIES} 次尝试")
                continue
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            html = page.content()
            tmp_soup = BeautifulSoup(html, "html.parser")
            has_records = bool(
                tmp_soup.select("tr.group")
                or tmp_soup.find("div", class_="js-aarecord-list-outer")
            )
            if has_records:
                soup = tmp_soup
                for tr in soup.select("tr.group"):
                    has_pdf = any(
                        s.get_text(strip=True).lower() == "pdf"
                        for s in tr.find_all("span")
                    )
                    if not has_pdf:
                        tr.decompose()
                break
            else:
                print(f"[WARN] 未获取到结果容器，第 {attempt}/{MAX_RETRIES} 次尝试")
        except Exception as e:
            print(f"[ERROR] 浏览器请求异常: {e}，第 {attempt}/{MAX_RETRIES} 次尝试")
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    head_links = ""
    if soup and soup.head:
        for tag in soup.head.find_all(["link", "script"]):
            if tag.name == "link" and tag.get("href") and tag["href"].startswith("/"):
                tag["href"] = origin + tag["href"]
            if tag.name == "script" and tag.get("src") and tag["src"].startswith("/"):
                tag["src"] = origin + tag["src"]
            head_links += str(tag)
    record_div = soup.find("div", class_="js-aarecord-list-outer") if soup else None
    return soup, head_links, record_div


def fetch_one_isbn_block(q: str) -> Tuple[Optional[BeautifulSoup], str, Optional[BeautifulSoup]]:
    """通过浏览器专用线程执行单个 ISBN 搜索（线程安全入口）。"""
    origin, base_url = get_aa_base_and_origin()
    future = _get_executor().submit(_fetch_one_sync, q, origin, base_url)
    return future.result(timeout=240)


def get_aa_base_and_origin() -> Tuple[str, str]:
    from backend.config import get_aa_origin, get_aa_base_url
    origin = get_aa_origin()
    base_url = get_aa_base_url()
    return origin, base_url


def absolutize_urls(root: BeautifulSoup, origin: str) -> None:
    for tag in root.find_all(href=True):
        href = tag["href"]
        if isinstance(href, str) and href.startswith("/"):
            tag["href"] = origin + href
    for tag in root.find_all(src=True):
        src = tag["src"]
        if isinstance(src, str) and src.startswith("/"):
            tag["src"] = origin + src



def strip_non_image_hrefs(root: BeautifulSoup) -> None:
    for a in root.find_all("a", href=True):
        if a.find("img"):
            a["target"] = "_blank"


def inject_checkboxes_and_headers(
    soup: BeautifulSoup,
    record_div: BeautifulSoup,
    file_label: str,
    check_first: bool = False,
) -> None:
    if not record_div:
        return

    rows = record_div.select("tr")
    processed_tables = set()
    for idx, row in enumerate(rows):
        img_href = ""
        img = row.find("img")
        if img:
            parent_a = img.find_parent("a", href=True)
            if parent_a:
                img_href = parent_a.get("href", "")
        if not img_href:
            any_a = row.find("a", href=True)
            if any_a:
                img_href = any_a.get("href", "")

        td = soup.new_tag("td", **{"class": "aa-select-cell"})
        cb_attrs = {
            "class": "select-item",
            "data-filename": file_label,
            "data-href": img_href,
        }
        if check_first and idx == 0:
            cb_attrs["checked"] = "checked"

        cb = soup.new_tag("input", type="checkbox", **cb_attrs)
        td.append(cb)

        first_td = row.find("td")
        if first_td:
            first_td.insert_before(td)
        else:
            row.insert(0, td)

        table = row.find_parent("table")
        if table and id(table) not in processed_tables:
            thead = table.find("thead")
            if thead:
                for trh in thead.find_all("tr"):
                    th = soup.new_tag("th", **{"class": "aa-select-th"})
                    trh.insert(0, th)
            processed_tables.add(id(table))


def build_aa_page_by_isbns(
    isbns: list[str],
    filename_map: dict[str, str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    from backend.config import get_aa_origin
    origin = get_aa_origin()

    results_html: list[str] = []
    css_js_links: str | None = None

    separator_html = """
        <div class="rainbow-separator" style="margin: 30px 0; text-align: center;">
            <hr style="border: none; height: 10px; background: linear-gradient(to right,
                #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
                border-radius: 3px; margin: 20px 0;">
            <div style="background: white; margin: -15px auto; width: 150px; padding: 0 15px;
                color: #333; font-weight: bold; font-size: 14px;">
            </div>
        </div>
        """

    for ind, key in enumerate(isbns):
        time.sleep(__import__("random").uniform(0.5, 0.8))
        print(f"AA搜索进度: {ind+1}/{len(isbns)}")
        if on_progress:
            on_progress(ind + 1, len(isbns))
        soup, head_links, record_div = fetch_one_isbn_block(key)

        if css_js_links is None:
            css_js_links = head_links or ""

        if not record_div:
            # fetch 失败（DDoS-Guard 挑战未通过/网络异常）：
            # 页面未正常返回结果容器。这并非"未找到结果"，
            # 需与真正无结果区分，避免误导并被错误缓存。
            results_html.append(
                '<div class="aa-result-block aa-search-failed">'
                f'<h2>搜索结果：{key}</h2>'
                '<p>AA 搜索失败（挑战未通过或网络异常），请稍后重试</p>'
                '</div>'
            )
            continue

        # 页面正常返回但结果容器内没有实际记录行（真正无结果）
        if not record_div.select("tr"):
            results_html.append(
                f'<div class="aa-result-block"><h2>搜索结果：{key}</h2><p>未找到结果</p></div>'
            )
            continue

        absolutize_urls(record_div, origin)
        file_label = (filename_map or {}).get(key) or f"{key}.pdf"
        inject_checkboxes_and_headers(soup, record_div, file_label, check_first=True)
        strip_non_image_hrefs(record_div)

        wrapper = soup.new_tag("div", **{"class": "js-aarecord-list-outer"})
        title = soup.new_tag("h2")
        title.string = f"搜索结果：{file_label}"
        wrapper.append(title)
        wrapper.append(record_div)

        additional_elements = soup.select(".js-aarecord-list-outer")
        for element in additional_elements:
            if id(element) == id(record_div):
                # record_div 已在 wrapper 中，避免重复追加
                continue
            absolutize_urls(element, origin)
            if record_div.find("td"):
                inject_checkboxes_and_headers(soup, element, file_label)
            else:
                inject_checkboxes_and_headers(soup, element, file_label, check_first=True)
            strip_non_image_hrefs(element)
            wrapper.append(element)

        results_html.append(separator_html)
        results_html.append(str(wrapper))

    results_html.append(separator_html)
    print("")
    return render_results_page(results_html, css_js_links or "", origin)


def render_results_page(results_blocks_html: list[str], css_js_links: str, origin: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>合并搜索结果</title>
{css_js_links or ""}
<style>
  .aa-page {{ max-width: 1200px; margin: 0 auto; padding: 12px; }}
  .aa-btn {{ padding: 8px 14px; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa; cursor: pointer; }}
  .aa-btn:hover {{ background: #eef1f4; }}
  .aa-select-cell {{ width: 36px; text-align: center; }}
  .aa-select-th {{ width: 36px; }}
  .aa-result-block {{ margin: 14px 0; }}
  .aa-hint {{ font-size: 12px; color: #666; }}
</style>
</head>
<body>
  <div class="aa-page">
    {"".join(results_blocks_html)}
  </div>
</body>
</html>"""
