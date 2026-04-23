import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; INDMoneyResearchBot/1.0; "
        "+https://app.example.com)"
    )
}
TIMEOUT = 15
MAX_RETRIES = 2


def fetch_url(url: str) -> str:
    """Fetch a URL and return clean plain text (HTML tags stripped)."""
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "head"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return " ".join(text.split())
        except requests.exceptions.RequestException as exc:
            if attempt > MAX_RETRIES:
                raise
            wait = 2 ** (attempt - 1)
            print(f"[url_loader] attempt {attempt} failed for {url}: {exc} — retrying in {wait}s")
            time.sleep(wait)
    return ""
