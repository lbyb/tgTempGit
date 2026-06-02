import re
import time
import random
import httpx
from typing import Optional, Dict
from bs4 import BeautifulSoup


def get_douban_cookies() -> Optional[Dict[str, str]]:
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


def simple_douban_request(
    url: str,
    max_retries: int = 3,
    cookies: Optional[Dict[str, str]] = None,
) -> Optional[str]:
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
                print(f"响应状态码: {response.status_code}", end="，")

                if response.status_code == 200:
                    content_length = len(response.content)
                    print(f"响应内容长度: {content_length} 字节", end="，")
                    if content_length < 1000:
                        print("响应内容过短，可能是错误页面")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            return None

                    for encoding in ["utf-8", "gbk", "gb2312"]:
                        try:
                            text = response.content.decode(encoding)
                            if "豆瓣" in text or "douban" in text.lower() or "series" in text.lower():
                                print(f"请求成功，使用编码: {encoding}", end="，")
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
    try:
        isbn_match = re.search(r"ISBN[：:]\s*</span>\s*([\dXx\-]+)", html_content)
        if not isbn_match:
            isbn_match = re.search(r"ISBN[：:]?\s*([\dXx\-]+)", html_content)

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

        translator_match = re.search(r"译者[：:].*?<a[^>]*>(.*?)</a>", html_content, re.DOTALL)
        translator = translator_match.group(1).strip() if translator_match else ""
        if translator:
            author = f"{author};{translator}" if author else translator

        author = author[:10] if len(author) > 10 else author

        year_match = re.search(r"出版年[：:]\s*</span>\s*([0-9]{4})", html_content)
        if not year_match:
            year_match = re.search(r"出版年[：:]?\s*([0-9]{4})", html_content)
        year = year_match.group(1) if year_match else ""

        page_match = re.search(r"页数[：:]\s*</span>\s*(\d+)", html_content)
        if not page_match:
            page_match = re.search(r"页数[：:]?\s*(\d+)", html_content)
        page_num = page_match.group(1) if page_match else ""

        original_isbn = isbn
        if page_num:
            isbn = f"P{page_num}-{isbn}"

        def clean_filename(s: str) -> str:
            return re.sub(r'[\\/:*?"<>|]+', "_", s)

        filename = f"{clean_filename(year)}-{clean_filename(author)}-{clean_filename(name)}-{clean_filename(isbn)}.pdf"

        return {
            "isbn": original_isbn,
            "name": name,
            "author": author,
            "year": year,
            "filename": filename,
        }

    except Exception as e:
        print(f"解析书籍信息时出错: {e}")
        return None


def get_books_from_series_new(series_url: str) -> Dict[str, str]:
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
        page_result = {}
        book_links = []

        selectors = [
            ".pic a[href]",
            ".subject-list .pic a[href]",
            ".cover a[href]",
            "a[href*='/subject/']",
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
            print(f"正在处理第 {i}/{len(book_links)} 本书: {href}", end="|")

            if href.startswith("/"):
                href = "https://book.douban.com" + href
            elif not href.startswith("http"):
                href = "https://book.douban.com/subject/" + href

            book_html = simple_douban_request(href, cookies=cookies)
            if not book_html:
                print(f"跳过书籍: {href}")
                continue

            try:
                book_info = parse_book_info(book_html)
                if book_info and book_info.get("isbn"):
                    page_result[book_info["isbn"]] = book_info["filename"]
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
                    if sibling.name == "a" and sibling.get("href"):
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
