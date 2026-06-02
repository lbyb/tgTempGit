# app.py
import re, time, asyncio, httpx, random, uvicorn, uuid, json
import urllib.parse
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from datetime import datetime, timedelta
import threading
import requests
from concurrent.futures import ThreadPoolExecutor

# 改进的请求头 - 更真实的浏览器模拟
DOUBAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Cache-Control": "max-age=0",
}

app = FastAPI(title="Douban Series + AA Merge (Async Version)")

# --- 配置 ---
url = f'http://38.150.35.28:32642/login'
try:
    response = requests.get(url, timeout=10)
except:
    time.sleep(30)
    response = requests.get(url, timeout=10)
hz = response.content.decode('utf-8')
if not hz or len(hz)>3:
    hz = 'li'
ORIGIN = f"https://annas-archive.{hz}"
BASE_URL = f"{ORIGIN}/search"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA}
DEFAULT_ISBNS = ["9787101066890", "9787807454908"]

# 任务存储（生产环境应该用Redis）
tasks_store = {}
executor = ThreadPoolExecutor(max_workers=5)

# --- 工具函数：AA 相关 ---
def absolutize_urls(root: BeautifulSoup):
    """把记录块里所有 / 开头的 href/src 改为绝对地址"""
    for tag in root.find_all(href=True):
        href = tag["href"]
        if isinstance(href, str) and href.startswith("/"):
            tag["href"] = ORIGIN + href
    for tag in root.find_all(src=True):
        src = tag["src"]
        if isinstance(src, str) and src.startswith("/"):
            tag["src"] = ORIGIN + src

def fetch_one_isbn_block(q: str):
    """请求单个 ISBN 的 AA 搜索结果"""
    params = {
        "index": "",
        "page": "1",
        "q": q,
        "display": "table",
        "ext": "pdf",
        "acc": "aa_download",
        "src": ["zlibzh", "duxiu"],
        "sort": ""
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    cookies = {
        "cf_clearance":"f1MzhSQD8lUb2wbxt7URYwMKjM6FoFLxsl2UfLtmP5Q-1756173850-1.2.1.1-JhajwA3IPlrbQS_JE3RRtRnmjaW4v.ix90XP5dPBYBIuM3wNSm8dQQFVSZhNtu36smhXwoijHYdlb.aN7fyr5QlKyZ_CYyOefQgoTKSKi9ioTKoNgZxA__alnW6fvA.rcEs7DEKIMy76Vb_VYOc3udKuq9y5X7oAte15Xc..pqVLTjlxK2EIIEuQMIQkH67YxdkLJvoqEadTwHgVOGmNDmVizNoJWXLnknOFvCXpXFw",
        "aa_account_id2":"eyJhIjoiQkVzNEpUZiIsImlhdCI6MTc1NTY0NTEwNH0.jsSPFHIuCk74ydP3lB0HcICmNmn2dubj_LpyixQ4YBg"
    }
    MAX_RETRIES = 9
    RETRY_DELAY = 3
    soup = None
    url = f'http://38.150.35.28:32642/login'
    try:
        response = requests.get(url, timeout=10)
    except:
        time.sleep(30)
        response = requests.get(url, timeout=10)
    hz = response.content.decode('utf-8')
    if not hz or len(hz)>3:
        hz = 'li'
    ORIGIN = f"https://annas-archive.{hz}"
    BASE_URL = f"{ORIGIN}/search"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(headers=HEADERS, timeout=30, cookies=cookies) as client:
                r = client.get(BASE_URL, params=params)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tr in soup.select('tr.group'):
                        has_pdf = any(s.get_text(strip=True).lower() == 'pdf' for s in tr.find_all('span'))
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
            time.sleep(RETRY_DELAY*attempt)

    head_links = "".join(str(tag) for tag in soup.head.find_all(["link", "script"])) if soup and soup.head else ""
    record_div = soup.find("div", class_="js-aarecord-list-outer") if soup else None
    return soup, head_links, record_div

def inject_checkboxes_and_headers(soup: BeautifulSoup, record_div: BeautifulSoup, file_label: str, check_first: bool = False):
    """为结果表格插入复选框和表头列"""
    if not record_div:
        return

    rows = record_div.select("tr")
    processed_tables = set()
    for idx, row in enumerate(rows):
        td = soup.new_tag("td", **{"class": "aa-select-cell"})
        cb_attrs = {
            "class": "select-item",
            "data-filename": file_label
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

# --- 工具函数：豆瓣相关 ---
def get_douban_cookies() -> Optional[Dict[str, str]]:
    """获取豆瓣cookies"""
    try:
        print("正在获取豆瓣cookies...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get("https://www.douban.com/", headers=headers)
            if response.status_code == 200:
                cookies = {}
                for cookie in response.cookies.jar:
                    cookies[cookie.name] = cookie.value
                print(f"成功获取 {len(cookies)} 个cookies")
                return cookies
            else:
                print(f"获取cookies失败，状态码: {response.status_code}")
                return None
    except Exception as e:
        print(f"获取cookies异常: {e}")
        return None

def simple_douban_request(url: str, max_retries: int = 3, cookies: Optional[Dict[str, str]] = None) -> Optional[str]:
    """改进的豆瓣请求函数，支持Cookie"""
    for attempt in range(max_retries):
        try:
            print(f"正在请求: {url} (尝试 {attempt + 1}/{max_retries})")
            headers_configs = [
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Referer": "https://www.douban.com/",
                },
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Connection": "keep-alive",
                    "Cache-Control": "max-age=0",
                    "Referer": "https://book.douban.com/",
                },
            ]
            
            headers = headers_configs[attempt % len(headers_configs)]
            if attempt > 0:
                delay = random.uniform(1.0, 1.5) + attempt * 3.0
                print(f"等待 {delay:.1f} 秒后重试...")
                time.sleep(delay)
            else:
                time.sleep(random.uniform(1.0, 1.5))
            
            timeout = 30 + attempt * 10
            with httpx.Client(timeout=timeout, follow_redirects=True, cookies=cookies) as client:
                response = client.get(url, headers=headers)
                print(f"响应状态码: {response.status_code}", end='，')
                
                if response.status_code == 200:
                    content_length = len(response.content)
                    print(f"响应内容长度: {content_length} 字节", end='，')
                    if content_length < 1000:
                        print("响应内容过短，可能是错误页面")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            return None
                    
                    for encoding in ['utf-8', 'gbk', 'gb2312']:
                        try:
                            text = response.content.decode(encoding)
                            if '豆瓣' in text or 'douban' in text.lower() or 'series' in text.lower():
                                print(f"请求成功，使用编码: {encoding}", end='，')
                                return text
                        except UnicodeDecodeError:
                            continue
                    
                    auto_text = response.text
                    if len(auto_text) > 1000:
                        print("使用自动编码")
                        return auto_text
                    else:
                        print("自动编码结果也过短")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            return None
                
                elif response.status_code == 403:
                    print(f"收到403错误 (尝试 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        print("可能触发反爬虫机制，将重新获取cookies并重试...")
                        new_cookies = get_douban_cookies()
                        if new_cookies:
                            cookies = new_cookies
                        continue
                    else:
                        return None
                
        except Exception as e:
            print(f"请求异常 (尝试 {attempt + 1}/{max_retries}): {e}")
        
        if attempt == max_retries - 1:
            print("所有重试都失败了")
            return None
    
    return None

def parse_book_info(html_content: str) -> Optional[Dict[str, str]]:
    """解析书籍详情页面信息"""
    try:
        isbn_match = re.search(r'ISBN[：:]\s*</span>\s*([\dXx\-]+)', html_content)
        if not isbn_match:
            isbn_match = re.search(r'ISBN[：:]?\s*([\dXx\-]+)', html_content)
        
        isbn = isbn_match.group(1).replace("-", "") if isbn_match else ""
        if not isbn:
            print("未找到ISBN")
            return None
        
        name_match = re.search(r'<span property="v:itemreviewed">(.*?)</span>', html_content)
        if not name_match:
            name_match = re.search(r'property="og:title"\s+content="([^"]+)"', html_content)
        
        name = name_match.group(1).strip() if name_match else ""
        
        soup = BeautifulSoup(html_content, "html.parser")
        author = ""
        
        author_span = soup.find("span", class_="pl", string=re.compile(r"作者|著"))
        if author_span:
            author_link = author_span.find_next("a")
            if author_link:
                author = re.sub(r"\s+", "", author_link.get_text())
        
        if not author:
            author_match = re.search(r'property="book:author"\s+content="([^"]+)"', html_content)
            author = author_match.group(1).strip() if author_match else ""
        
        translator_match = re.search(r'译者[：:].*?<a[^>]*>(.*?)</a>', html_content, re.DOTALL)
        translator = translator_match.group(1).strip() if translator_match else ""
        if translator:
            author = f"{author};{translator}" if author else translator
        
        author = author[:10] if len(author) > 10 else author
        
        year_match = re.search(r'出版年[：:]\s*</span>\s*([0-9]{4})', html_content)
        if not year_match:
            year_match = re.search(r'出版年[：:]?\s*([0-9]{4})', html_content)
        year = year_match.group(1) if year_match else ""
        
        page_match = re.search(r'页数[：:]\s*</span>\s*(\d+)', html_content)
        if not page_match:
            page_match = re.search(r'页数[：:]?\s*(\d+)', html_content)
        page_num = page_match.group(1) if page_match else ""
        
        original_isbn = isbn
        if page_num:
            isbn = f"P{page_num}-{isbn}"
        
        def clean_filename(s: str) -> str:
            return re.sub(r'[\\/:*?"<>|]+', "_", s)
        
        filename = f"{clean_filename(year)}-{clean_filename(author)}-{clean_filename(name)}-{clean_filename(isbn)}.pdf"
        
        return {
            'isbn': original_isbn,
            'name': name,
            'author': author,
            'year': year,
            'filename': filename
        }
        
    except Exception as e:
        print(f"解析书籍信息时出错: {e}")
        return None

def get_books_from_series_new(series_url: str) -> Dict[str, str]:
    """简化的豆瓣系列抓取函数，支持Cookie"""
    result: Dict[str, str] = {}
    
    print(f"开始抓取豆瓣丛书: {series_url}")
    
    cookies = get_douban_cookies()
    if not cookies:
        print("警告：未能获取cookies，将在没有cookies的情况下尝试")
    
    html = simple_douban_request(series_url, cookies=cookies)
    if not html:
        print("无法获取系列页面")
        return result
    
    print(f"HTML长度: {len(html)} 字符")
    
    soup = BeautifulSoup(html, "html.parser")
    
    def parse_page_books(page_soup: BeautifulSoup, page_url: str) -> Dict[str, str]:
        """解析单页的书籍"""
        page_result = {}
        book_links = []
        
        selectors = [
            ".pic a[href]",
            ".subject-list .pic a[href]",
            ".cover a[href]",
            "a[href*='/subject/']"
        ]
        
        for selector in selectors:
            links = page_soup.select(selector)
            if links:
                print(f"使用选择器 '{selector}' 找到 {len(links)} 个链接")
                for a in links:
                    href = a.get("href", "")
                    if "/subject/" in href and href not in book_links:
                        book_links.append(href)
                break
        
        if not book_links:
            print("未找到任何书籍链接")
            return page_result
        
        print(f"在页面找到 {len(book_links)} 本书")
        
        for i, href in enumerate(book_links, 1):
            print(f"正在处理第 {i}/{len(book_links)} 本书: {href}", end='|')
            
            if href.startswith('/'):
                href = "https://book.douban.com" + href
            elif not href.startswith('http'):
                href = "https://book.douban.com/subject/" + href
            
            book_html = simple_douban_request(href, cookies=cookies)
            if not book_html:
                print(f"跳过书籍: {href}")
                continue
            
            try:
                book_info = parse_book_info(book_html)
                if book_info and book_info.get('isbn'):
                    page_result[book_info['isbn']] = book_info['filename']
                    print(f"成功解析: {book_info.get('name', '未知书名')}")
                else:
                    print("解析失败：未找到ISBN或其他必要信息")
                    
            except Exception as e:
                print(f"解析书籍信息出错: {e}")
            
            time.sleep(random.uniform(0.5, 0.9))
        
        return page_result
    
    result.update(parse_page_books(soup, series_url))
    
    try:
        paginator = soup.find("div", class_="paginator")
        if paginator:
            print("检测到分页，正在分析分页结构...")
            
            last_page = 1
            
            next_span = paginator.find("span", class_="next")
            if next_span:
                prev_links = []
                for sibling in next_span.previous_siblings:
                    if sibling.name == 'a' and sibling.get('href'):
                        prev_links.append(sibling)
                
                if prev_links:
                    last_link = prev_links[0]
                    last_text = last_link.get_text().strip()
                    if last_text.isdigit():
                        last_page = int(last_text)
                        print(f"通过next前链接发现最后页码: {last_page}")
            
            if last_page == 1:
                page_numbers = []
                for a in paginator.find_all("a", href=True):
                    text = a.get_text().strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                
                if page_numbers:
                    last_page = max(page_numbers)
                    print(f"通过数字链接发现最后页码: {last_page}")
            
            print(f"检测到总共 {last_page} 页")
            print(f"将处理所有 {last_page} 页")
            
            page_urls = []
            for page_num in range(2, last_page + 1):
                page_url = f"{series_url}?page={page_num}"
                page_urls.append((page_num, page_url))
            
            print(f"将处理额外 {len(page_urls)} 个分页")
            
            for i, (page_num, page_url) in enumerate(page_urls, 1):
                print(f"正在处理第 {page_num} 页 ({i}/{len(page_urls)}): {page_url}")
                page_html = simple_douban_request(page_url, cookies=cookies)
                if page_html:
                    page_soup = BeautifulSoup(page_html, "html.parser")
                    page_books = parse_page_books(page_soup, page_url)
                    result.update(page_books)
                    print(f"第 {page_num} 页处理完成，新增 {len(page_books)} 本书，累计 {len(result)} 本书")
                else:
                    print(f"第 {page_num} 页获取失败")
                
                if last_page > 20:
                    delay = random.uniform(2.0, 3.0)
                else:
                    delay = random.uniform(1, 2)
                
                print(f"等待 {delay:.1f} 秒后继续...")
                time.sleep(delay)
        else:
            print("未检测到分页")
    except Exception as e:
        print(f"处理分页时出错: {e}")
    
    print(f"抓取完成，共获得 {len(result)} 本书")
    return result

# --- 页面渲染 ---
def render_results_page(results_blocks_html: List[str], css_js_links: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>合并搜索结果</title>
<base href="{ORIGIN}/" target="_blank">
{css_js_links or ""}
<style>
  .aa-page {{ max-width: 1200px; margin: 0 auto; padding: 12px; }}
  .aa-toolbar {{ position: sticky; top: 0; z-index: 999; display: flex; justify-content: center; gap: 10px; background: #fff; padding: 10px; border-bottom: 1px solid #eee; }}
  .aa-btn {{ padding: 8px 14px; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa; cursor: pointer; }}
  .aa-btn:hover {{ background: #eef1f4; }}
  .aa-select-cell {{ width: 36px; text-align: center; }}
  .aa-select-th {{ width: 36px; }}
  .aa-result-block {{ margin: 14px 0; }}
  .aa-hint {{ font-size: 12px; color: #666; }}
</style>
<script>
function getRowMainLink(row) {{
  return row.querySelector('a[href*="/md5/"]') || row.querySelector('a[href]');
}}
async function copyTextWithFallback(text, okMsg) {{
  try {{
    if (navigator.clipboard && window.isSecureContext) {{
      await navigator.clipboard.writeText(text);
    }} else {{
      const ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly','');
      ta.style.position='absolute'; ta.style.left='-9999px';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
    }}
    alert(okMsg);
  }} catch (e) {{
    alert(okMsg + '（兼容模式）');
  }}
}}
function copySelected() {{
  const boxes = document.querySelectorAll('.select-item:checked');
  const lines = [];
  boxes.forEach(cb => {{
    const row = cb.closest('tr');
    if (!row) return;
    const link = getRowMainLink(row);
    if (!link) return;
    let abs = '';
    try {{
      abs = new URL(link.getAttribute('href'), document.baseURI).href;
    }} catch (e) {{
      abs = link.href;
    }}
    const fname = cb.dataset.filename || '';
    lines.push(abs + ' |' + fname);
  }});
  copyTextWithFallback(lines.join('\\n'), '已复制 ' + lines.length + ' 项');
}}
</script>
</head>
<body>
  <div class="aa-page">
    <div class="aa-toolbar">
      <button class="aa-btn" onclick="copySelected()">复制选中链接</button>
      <span class="aa-hint">（勾选后点击复制，每行格式：链接&&&文件名）</span>
    </div>
    {"".join(results_blocks_html)}
  </div>
</body>
</html>"""

def build_aa_page_by_isbns(isbns: List[str], filename_map: Optional[Dict[str, str]] = None) -> str:
    results_html: List[str] = []
    css_js_links: Optional[str] = None

    for ind, key in enumerate(isbns):
        time.sleep(random.uniform(0.5, 0.8))
        print(f'\r{ind+1}', end="", flush=True)
        soup, head_links, record_div = fetch_one_isbn_block(key)

        if css_js_links is None:
            css_js_links = head_links or ""

        if not record_div:
            results_html.append(f'<div class="aa-result-block"><h2>搜索结果：{key}</h2><p>未找到结果</p></div>')
            continue

        absolutize_urls(record_div)
        file_label = (filename_map or {}).get(key) or f"{key}.pdf"
        inject_checkboxes_and_headers(soup, record_div, file_label, check_first=True)

        wrapper = soup.new_tag("div", **{"class": "js-aarecord-list-outer"})
        title = soup.new_tag("h2")
        title.string = f"搜索结果：{file_label}"
        wrapper.append(title)
        wrapper.append(record_div)

        additional_elements = soup.select(".js-aarecord-list-outer")
        for element in additional_elements:
            absolutize_urls(element)
            if record_div.find('td'):
                inject_checkboxes_and_headers(soup, element, file_label)
            else:
                inject_checkboxes_and_headers(soup, element, file_label, check_first=True)
            wrapper.append(element)

        separator_html = '''
            <div class="rainbow-separator" style="margin: 30px 0; text-align: center;">
                <hr style="border: none; height: 10px; background: linear-gradient(to right, 
                    #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3); 
                    border-radius: 3px; margin: 20px 0;">
                <div style="background: white; margin: -15px auto; width: 150px; padding: 0 15px; 
                    color: #333; font-weight: bold; font-size: 14px;">
                </div>
            </div>
            '''
        results_html.append(separator_html)
        results_html.append(str(wrapper))

    results_html.append(separator_html)
    print('')
    return render_results_page(results_html, css_js_links or "")

# --- 异步任务处理 ---
def process_series_task(task_id: str, series_urls: List[str]):
    """后台处理series任务"""
    try:
        tasks_store[task_id]['status'] = 'processing'
        tasks_store[task_id]['start_time'] = datetime.now()
        
        all_books = {}
        processed_series = []
        
        for idx, series_url in enumerate(series_urls, 1):
            tasks_store[task_id]['current_series'] = idx
            tasks_store[task_id]['current_url'] = series_url
            
            # 处理每个series
            books = get_books_from_series_new(series_url)
            if books:
                all_books.update(books)
                processed_series.append(series_url)
            
            # 如果有多个series，添加延时
            if idx < len(series_urls):
                print(f"处理完第 {idx} 个series，等待60秒...")
                time.sleep(60)
        
        # 生成结果HTML
        if all_books:
            filename_map = {}
            keys = []
            for isbn, filename in all_books.items():
                keys.append(isbn)
                filename_map[isbn] = filename
            
            html = build_aa_page_by_isbns(keys, filename_map)
            tasks_store[task_id]['result'] = html
            tasks_store[task_id]['status'] = 'completed'
            tasks_store[task_id]['total_books'] = len(all_books)
        else:
            tasks_store[task_id]['status'] = 'failed'
            tasks_store[task_id]['error'] = '未找到任何书籍'
            
    except Exception as e:
        tasks_store[task_id]['status'] = 'failed'
        tasks_store[task_id]['error'] = str(e)
        print(f"任务 {task_id} 处理失败: {e}")
    finally:
        tasks_store[task_id]['end_time'] = datetime.now()

# --- 路由 ---
@app.get("/", response_class=HTMLResponse)
def index():
    """统一入口页面"""
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>豆瓣丛书 → AA 合并搜索</title>
<style>
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 24px; }}
  .topbar {{ position: sticky; top: 0; background:#fff; padding: 12px 8px; border-bottom: 1px solid #eee; z-index: 999; }}
  .form {{ display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; }}
  .input {{ padding: 8px 10px; border: 1px solid #d0d7de; border-radius: 8px; }}
  .btn {{ padding: 8px 14px; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa; cursor: pointer; }}
  .btn:hover {{ background: #eef1f4; }}
  .help {{ font-size: 12px; color: #666; margin-top: 8px; }}
  .sec {{ margin-top: 18px; }}
  .label {{ font-weight: 600; margin-bottom: 6px; }}
  .notice {{ background: #fff3cd; border: 1px solid #ffeb3b; padding: 10px; border-radius: 5px; margin-top: 10px; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar"><h2>豆瓣丛书 → AA 合并搜索</h2></div>

    <form class="form" action="/search" method="get">
      <div>
        <div class="label">方式一：豆瓣丛书URL（支持逗号分隔多个）</div>
        <input class="input" name="series_url" placeholder="如：https://book.douban.com/series/1300,https://book.douban.com/series/1301" />
        <div class="help">支持输入多个series URL，用逗号分隔。处理多个series时每个之间会延时1分钟。</div>

        <div class="sec label">方式二：手动输入 ISBN（逗号或空格分隔）</div>
        <input class="input" name="isbns" placeholder="如：9787101066890,9787807454908" value="{','.join(DEFAULT_ISBNS)}" />
        <div class="help">若同时填写丛书URL与ISBN，则优先使用丛书URL。</div>
      </div>
      <button class="btn" type="submit">合并搜索结果</button>
    </form>
    
    <div class="notice">
      <strong>注意：</strong>处理豆瓣丛书需要时间，提交后页面会显示进度，请耐心等待。
    </div>
  </div>
</body>
</html>
"""
    return HTMLResponse(html)

@app.get("/search", response_class=HTMLResponse)
def search(series_url: Optional[str] = Query(None), isbns: Optional[str] = Query(None)):
    
    if series_url:
        # 解析多个series URL
        series_urls = []
        for url in series_url.split(','):
            url = url.strip()
            if url:
                match = re.match(r"^(\d+)-", url)
                if match:
                    series_id = match.group(1)
                    url = f"https://book.douban.com/series/{series_id}"
                series_urls.append(url)
        
        if series_urls:
            # 创建任务
            task_id = str(uuid.uuid4())
            tasks_store[task_id] = {
                'status': 'pending',
                'total_series': len(series_urls),
                'current_series': 0,
                'result': None,
                'error': None
            }
            
            # 在后台线程执行任务
            executor.submit(process_series_task, task_id, series_urls)
            
            # 返回进度页面
            return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>处理中...</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
  .progress {{ background: #f0f0f0; border-radius: 5px; padding: 20px; margin: 20px 0; }}
  .status {{ font-size: 18px; margin: 10px 0; }}
  .spinner {{ display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f3f3; border-top: 3px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite; }}
  @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
  .error {{ color: red; font-weight: bold; }}
  .success {{ color: green; font-weight: bold; }}
</style>
<script>
async function checkStatus() {{
  try {{
    const response = await fetch('/task/{task_id}');
    const data = await response.json();
    
    const statusDiv = document.getElementById('status');
    if (data.status === 'processing') {{
      statusDiv.innerHTML = `
        <div class="spinner"></div>
        <p>正在处理第 ${{data.current_series}}/${{data.total_series}} 个系列...</p>
        <p>当前URL: ${{data.current_url || ''}}</p>
      `;
      setTimeout(checkStatus, 2000);
    }} else if (data.status === 'completed') {{
      statusDiv.innerHTML = '<p class="success">处理完成！正在跳转到结果页面...</p>';
      window.location.href = '/result/{task_id}';
    }} else if (data.status === 'failed') {{
      statusDiv.innerHTML = `<p class="error">处理失败: ${{data.error}}</p>`;
    }} else {{
      statusDiv.innerHTML = '<p>等待处理...</p>';
      setTimeout(checkStatus, 2000);
    }}
  }} catch (error) {{
    console.error('Error checking status:', error);
    setTimeout(checkStatus, 5000);
  }}
}}

// 开始检查状态
checkStatus();
</script>
</head>
<body>
  <h1>正在处理豆瓣丛书...</h1>
  <div class="progress">
    <div id="status" class="status">
      <div class="spinner"></div>
      <p>初始化中...</p>
    </div>
  </div>
  <p>提示：处理多个系列时，每个系列之间会延时1分钟，请耐心等待。</p>
</body>
</html>""")

    if isbns:
        parts = [p for p in re.split(r"[,\s;]+", isbns.strip()) if p]
        html = build_aa_page_by_isbns(parts)
        return HTMLResponse(html)

    return index()

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks_store:
        return JSONResponse({"status": "not_found"})
    
    task = tasks_store[task_id]
    return JSONResponse({
        "status": task["status"],
        "total_series": task.get("total_series", 0),
        "current_series": task.get("current_series", 0),
        "current_url": task.get("current_url", ""),
        "error": task.get("error", None),
        "total_books": task.get("total_books", 0)
    })

@app.get("/result/{task_id}", response_class=HTMLResponse)
def get_result(task_id: str):
    print("\a", end="", flush=True)
    """获取任务结果"""
    if task_id not in tasks_store:
        return HTMLResponse("<p>任务不存在</p>")
    
    task = tasks_store[task_id]
    if task["status"] == "completed" and task["result"]:
        return HTMLResponse(task["result"])
    elif task["status"] == "failed":
        return HTMLResponse(f"<p>处理失败: {task.get('error', '未知错误')}</p>")
    else:
        # 如果还在处理，重定向到状态页面
        return HTMLResponse(f"""
        <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/search?task_id={task_id}">
        </head>
        <body>
            正在重定向...
        </body>
        </html>
        """)

# 清理过期任务（可选）
@app.on_event("startup")
async def startup_event():
    """定期清理过期任务"""
    async def cleanup_tasks():
        while True:
            await asyncio.sleep(300)  # 每小时清理一次
            now = datetime.now()
            expired = []
            for task_id, task in tasks_store.items():
                if 'end_time' in task:
                    if (now - task['end_time']).seconds > 200:  # 2小时后过期
                        expired.append(task_id)
            for task_id in expired:
                del tasks_store[task_id]
                print(f"清理过期任务: {task_id}")
    
    asyncio.create_task(cleanup_tasks())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
