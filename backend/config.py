import time
import os
import requests

LOGIN_URL = "http://www.lbylkylin.vip/login"

SECRET_TOKEN = os.getenv("APP_SECRET_TOKEN", "lby")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

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

DEFAULT_ISBNS = ["9787101066890", "9787807454908"]

AA_HEADERS = {"User-Agent": UA}

AA_COOKIES = {
    "cf_clearance": "f1MzhSQD8lUb2wbxt7URYwMKjM6FoFLxsl2UfLtmP5Q-1756173850-1.2.1.1-JhajwA3IPlrbQS_JE3RRtRnmjaW4v.ix90XP5dPBYBIuM3wNSm8dQQFVSZhNtu36smhXwoijHYdlb.aN7fyr5QlKyZ_CYyOefQgoTKSKi9ioTKoNgZxA__alnW6fvA.rcEs7DEKIMy76Vb_VYOc3udKuq9y5X7oAte15Xc..pqVLTjlxK2EIIEuQMIQkH67YxdkLJvoqEadTwHgVOGmNDmVizNoJWXLnknOFvCXpXFw",
    "aa_account_id2": "eyJhIjoiQkVzNEpUZiIsImlhdCI6MTc1NTY0NTEwNH0.jsSPFHIuCk74ydP3lB0HcICmNmn2dubj_LpyixQ4YBg",
}

MAX_WORKERS = 5

MAX_RETRIES = 9
RETRY_DELAY = 3


def get_aa_origin() -> str:
    for attempt in range(2):
        try:
            response = requests.get(LOGIN_URL, timeout=10)
            hz = response.content.decode("utf-8")
            if hz and len(hz) <= 3:
                return f"https://annas-archive.{hz}"
        except Exception:
            if attempt == 0:
                time.sleep(30)
    return "https://annas-archive.li"


def get_aa_base_url() -> str:
    return f"{get_aa_origin()}/search"
