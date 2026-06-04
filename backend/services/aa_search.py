import time
import httpx
from typing import Optional, Tuple, Callable
from bs4 import BeautifulSoup

from backend.config import (
    AA_HEADERS,
    AA_COOKIES,
    MAX_RETRIES,
    RETRY_DELAY,
)


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


def fetch_one_isbn_block(q: str) -> Tuple[Optional[BeautifulSoup], str, Optional[BeautifulSoup]]:
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    origin, base_url = get_aa_base_and_origin()
    soup = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(headers=AA_HEADERS, timeout=30, cookies=AA_COOKIES) as client:
                r = client.get(base_url, params=params)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tr in soup.select("tr.group"):
                        has_pdf = any(s.get_text(strip=True).lower() == "pdf" for s in tr.find_all("span"))
                        if not has_pdf:
                            tr.decompose()
                    break
                else:
                    print(f"[WARN] 请求失败 {r.status_code}，第 {attempt}/{MAX_RETRIES} 次尝试")
        except httpx.RequestError as e:
            print(f"[ERROR] 网络异常: {e}，第 {attempt}/{MAX_RETRIES} 次尝试")
        except Exception as e:
            print(f"[ERROR] 未知异常: {e}，第 {attempt}/{MAX_RETRIES} 次尝试")
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
            results_html.append(f'<div class="aa-result-block"><h2>搜索结果：{key}</h2><p>未找到结果</p></div>')
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
