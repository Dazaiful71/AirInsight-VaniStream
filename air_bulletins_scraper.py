import argparse
import calendar
import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.robotparser
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import requests
from bs4 import BeautifulSoup


def _add_nvidia_dll_dirs() -> None:
    """Windows: make the cuBLAS / cuDNN DLLs from the `nvidia-*-cu12` pip packages findable
    by ctranslate2 (they live in site-packages/nvidia/<pkg>/bin, which is not on PATH)."""
    if os.name != "nt":
        return
    import site
    roots = set(site.getsitepackages() + [site.getusersitepackages()])
    for root in roots:
        nv = os.path.join(root, "nvidia")
        if not os.path.isdir(nv):
            continue
        for name in os.listdir(nv):
            bin_dir = os.path.join(nv, name, "bin")
            if os.path.isdir(bin_dir):
                try:
                    os.add_dll_directory(bin_dir)
                except OSError:
                    pass
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


_add_nvidia_dll_dirs()

BASE_URL ="https://newsonair.gov.in"
PAGE_URL = BASE_URL + "/audio-archive-search/"
ROBOTS_URL = BASE_URL + "/robots.txt"
AJAX_URL = BASE_URL + "/wp-admin/admin-ajax.php"
# Headers the archive page's own JavaScript sends with every AJAX call.
AJAX_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]
DEFAULT_UA = USER_AGENTS[0]


def rotate_user_agent(session: requests.Session) -> None:
    """Randomly rotate user agent on session."""
    session.headers["User-Agent"] = random.choice(USER_AGENTS)


def check_robots_txt(session: requests.Session, target_url: str = AJAX_URL) -> bool:
    """Return True only if robots.txt allows both the archive page and the AJAX endpoint.

    A missing robots.txt (404) counts as allowed. Any other failure to read it, or a
    disallow rule, returns False and the caller must stop the crawl.
    """
    try:
        resp = session.get(ROBOTS_URL, timeout=15)
    except requests.RequestException as e:
        print(f"STOP: could not fetch robots.txt ({e}); not crawling without verifying it.")
        return False
    if resp.status_code == 404:
        print("robots.txt not found (404): no restrictions published.")
        return True
    if resp.status_code != 200:
        print(f"STOP: robots.txt returned HTTP {resp.status_code}; not crawling without verifying it.")
        return False
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())
    ua = session.headers.get("User-Agent", "*")
    for url in (PAGE_URL, target_url):
        if not rp.can_fetch(ua, url):
            print(f"STOP: robots.txt disallows fetching {url} for this user agent.")
            return False
    print("robots.txt check passed: scraping allowed.")
    return True


@dataclass(frozen=True)
class BulletinItem:
    title: str
    date_text: str
    date_iso: Optional[str]
    audio_url: str
    time_hint: Optional[int]  # valid HHMM from the filename (e.g. 2305), else None
    hour: Optional[int] = None  # 0-23 = time_hint // 100, else None (never 0 as a placeholder)
    hour_flag: str = "ok"  # ok | no_time_in_filename | invalid_hhmm
    page: int = 0


def sleep_jitter(min_delay: float, max_delay: float) -> None:
    if max_delay <= 0:
        return
    time.sleep(random.uniform(min_delay, max_delay))


def sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_date_text(date_text: str) -> Optional[str]:
    try:
        parsed = dt.datetime.strptime(date_text.strip(), "%d %B %Y").date()
        return parsed.isoformat()
    except ValueError:
        return None


def parse_hour_from_url(audio_url: str) -> Tuple[Optional[int], Optional[int], str]:
    """Return (hhmm, hour, flag) from the first standalone 4-digit group in the filename.

    Valid HHMM (hour 00-23, minute 00-59) gives hour = hhmm // 100. Otherwise hhmm and
    hour are None (never 0) and the flag says why.
    """
    base = os.path.splitext(os.path.basename(audio_url))[0]
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", base)
    if not match:
        return None, None, "no_time_in_filename"
    hhmm = int(match.group(1))
    if hhmm // 100 > 23 or hhmm % 100 > 59:
        return None, None, "invalid_hhmm"
    return hhmm, hhmm // 100, "ok"


def extract_time_hint(audio_url: str) -> Optional[int]:
    """Valid HHMM from the filename, or None."""
    return parse_hour_from_url(audio_url)[0]


def estimate_minutes(audio_url: str) -> Optional[int]:
    """Duration in minutes from a 'HHMM-HHMM' filename pattern (e.g. English-2305-2310-18), else None."""
    base = os.path.splitext(os.path.basename(audio_url))[0]
    m = re.search(r"(?<!\d)(\d{4})-(\d{4})(?!\d)", base)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if a // 100 > 23 or a % 100 > 59 or b // 100 > 23 or b % 100 > 59:
        return None
    minutes = (b // 100 * 60 + b % 100) - (a // 100 * 60 + a % 100)
    if minutes <= 0:
        minutes += 24 * 60
    return minutes if minutes <= 60 else None


def make_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    session.nonce = None  # WordPress nonce, read fresh from the archive page
    return session


def extract_nonce(page_html: str, action: str = "filter_bulletins_audio") -> str:
    """Read the `security` nonce embedded in the archive page's inline JavaScript."""
    m = re.search(
        r"action:\s*['\"]" + re.escape(action) + r"['\"]\s*,\s*security:\s*['\"]([^'\"]+)['\"]",
        page_html,
    )
    if not m:
        m = re.search(r"security:\s*['\"]([0-9a-fA-F]+)['\"]", page_html)
    if not m:
        raise RuntimeError("no `security` nonce found in the archive page (site layout changed?)")
    return m.group(1)


def ensure_nonce(session: requests.Session, timeout: int = 30, force: bool = False) -> str:
    if force or not getattr(session, "nonce", None):
        resp = session.get(PAGE_URL, timeout=timeout)
        resp.raise_for_status()
        session.nonce = extract_nonce(resp.text)
    return session.nonce


def post_ajax(
    session: requests.Session,
    payload: dict,
    timeout: int,
    max_retries: int,
    min_delay: float,
    max_delay: float,
) -> str:
    rotate_user_agent(session)
    nonce_refreshed = False
    for attempt in range(1, max_retries + 1):
        try:
            body = dict(payload)
            body.setdefault("security", ensure_nonce(session, timeout))
            resp = session.post(AJAX_URL, data=body, headers=AJAX_HEADERS, timeout=timeout)
            if resp.status_code == 403 and not nonce_refreshed:
                nonce_refreshed = True  # the nonce may have expired: refresh it once
                ensure_nonce(session, timeout, force=True)
                continue
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            if attempt >= max_retries:
                raise
            sleep_jitter(min_delay, max_delay)
    raise RuntimeError("Unreachable retry loop")


def fetch_categories(
    session: requests.Session,
    language: str,
    timeout: int,
    max_retries: int,
    min_delay: float,
    max_delay: float,
) -> list[tuple[str, str]]:
    html = post_ajax(
        session,
        {"action": "get_listen_news_categories", "language": language},
        timeout,
        max_retries,
        min_delay,
        max_delay,
    )
    soup = BeautifulSoup(html, "html.parser")
    options = []
    for opt in soup.select("option"):
        value = (opt.get("value") or "").strip()
        label = opt.get_text(strip=True)
        if not value:
            continue
        options.append((value, label))
    return options


def parse_bulletins(html: str, page: int = 0) -> tuple[list[BulletinItem], bool]:
    soup = BeautifulSoup(html, "html.parser")
    no_posts = soup.get_text(" ", strip=True).lower().startswith("no posts found")
    if no_posts:
        return [], False

    items: list[BulletinItem] = []
    for li in soup.select("li"):
        source = li.select_one("audio source")
        if not source:
            continue
        audio_url = (source.get("src") or "").strip()
        if not audio_url:
            continue
        title_el = li.select_one("h3")
        date_el = li.select_one("p")
        title = title_el.get_text(strip=True) if title_el else ""
        date_text = date_el.get_text(strip=True) if date_el else ""
        date_iso = parse_date_text(date_text)
        hhmm, hour, flag = parse_hour_from_url(audio_url)
        items.append(
            BulletinItem(
                title=title,
                date_text=date_text,
                date_iso=date_iso,
                audio_url=audio_url,
                time_hint=hhmm,
                hour=hour,
                hour_flag=flag,
                page=page,
            )
        )

    has_next = soup.select_one("nav.pagination a.next") is not None
    return items, has_next


def fetch_bulletins(
    session: requests.Session,
    language: str,
    category: str,
    date_from: str,
    date_to: str,
    timeout: int,
    max_retries: int,
    min_delay: float,
    max_delay: float,
    max_pages: int,
) -> tuple[list[BulletinItem], bool]:
    """Fetch every page for ONE query. date_from / date_to are the site's raw bounds,
    which are EXCLUSIVE on both ends (see make_windows). Returns (items, truncated)."""
    all_items: list[BulletinItem] = []
    page = 1
    truncated = False
    while True:
        payload = {
            "action": "filter_bulletins_audio",
            "language": language,
            "category": category,
            "date_from": date_from,
            "date_to": date_to,
            "paged": str(page),
        }
        html = post_ajax(session, payload, timeout, max_retries, min_delay, max_delay)
        items, has_next = parse_bulletins(html, page)
        if not items:
            break
        all_items.extend(items)
        if not has_next:
            break
        if page >= max_pages:
            truncated = True
            break
        page += 1
        sleep_jitter(min_delay, max_delay)
    return all_items, truncated


# ---------------------------------------------------------------------------
# Date windows. Found in step S3c: the site's date_from and date_to are EXCLUSIVE.
# To get days D1..Dn (inclusive) query (D1 - 1 day, Dn + 1 day). Consecutive windows
# a..b and b+1..c therefore use (a-1, b+1) and (b, c+1): the shared dates are excluded
# bounds, so no day is skipped and none is counted twice.
# ---------------------------------------------------------------------------

def make_windows(first_day: dt.date, last_day: dt.date, span_days: int = 7) -> list[dict]:
    """Split the inclusive day range into windows of up to span_days days."""
    windows = []
    start = first_day
    while start <= last_day:
        end = min(start + dt.timedelta(days=span_days - 1), last_day)
        windows.append({
            "first": start,
            "last": end,
            "query_from": (start - dt.timedelta(days=1)).isoformat(),
            "query_to": (end + dt.timedelta(days=1)).isoformat(),
        })
        start = end + dt.timedelta(days=1)
    return windows


def crawl_windows(
    session: requests.Session,
    windows: list[dict],
    language: str,
    category: str,
    timeout: int,
    max_retries: int,
    min_delay: float,
    max_delay: float,
    max_pages: int,
) -> list[BulletinItem]:
    """Crawl each window; drop items outside its days, de-duplicate by audio_url."""
    items_out: list[BulletinItem] = []
    seen: set[str] = set()
    for w in windows:
        items, truncated = fetch_bulletins(
            session, language, category, w["query_from"], w["query_to"],
            timeout, max_retries, min_delay, max_delay, max_pages,
        )
        first, last = w["first"].isoformat(), w["last"].isoformat()
        inside = [i for i in items if i.date_iso and first <= i.date_iso <= last]
        outside = len(items) - len(inside)
        dup = 0
        for it in inside:
            if it.audio_url in seen:
                dup += 1
                continue
            seen.add(it.audio_url)
            items_out.append(it)
        pages = max((i.page for i in items), default=0)
        print(f"window {first}..{last} (query {w['query_from']} / {w['query_to']}): "
              f"{len(items)} items, {pages} pages, {outside} outside days, {dup} duplicates")
        if truncated:
            print(f"  WARNING: hit --max-pages ({max_pages}) with more pages left: window truncated")
        if outside:
            print("  WARNING: items outside the window's days; the date-bound rule may have changed")
        sleep_jitter(min_delay, max_delay)
    return items_out


def report_day_counts(items: list[BulletinItem], first_day: dt.date, last_day: dt.date) -> list[str]:
    """Print the item count per day and return the days with 0 items."""
    counts: dict[str, int] = {}
    for it in items:
        key = it.date_iso or "unparsed"
        counts[key] = counts.get(key, 0) + 1
    zero_days = []
    print("\nItems per day:")
    day = first_day
    while day <= last_day:
        iso = day.isoformat()
        n = counts.get(iso, 0)
        print(f"  {iso} ({day.strftime('%a')}): {n}")
        if n == 0:
            zero_days.append(iso)
        day += dt.timedelta(days=1)
    if counts.get("unparsed"):
        print(f"  unparsed dates: {counts['unparsed']}")
    print(f"Total items: {len(items)}")
    print("Days with 0 items:", ", ".join(zero_days) if zero_days else "none")
    return zero_days


LISTING_FIELDS = ["date", "title", "audio_url", "time_hint", "hour", "hour_flag",
                  "language", "category", "page", "window"]


def write_listing_csv(path: str, items: list[BulletinItem], language: str, category: str,
                      windows: list[dict]) -> None:
    def window_of(iso: Optional[str]) -> str:
        for w in windows:
            if iso and w["first"].isoformat() <= iso <= w["last"].isoformat():
                return f"{w['first']}..{w['last']}"
        return ""

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LISTING_FIELDS)
        writer.writeheader()
        for it in items:
            writer.writerow({
                "date": it.date_iso or it.date_text,
                "title": it.title,
                "audio_url": it.audio_url,
                "time_hint": "" if it.time_hint is None else it.time_hint,
                "hour": "" if it.hour is None else it.hour,  # empty, never 0, when unknown
                "hour_flag": it.hour_flag,
                "language": language,
                "category": category or "all",
                "page": it.page,
                "window": window_of(it.date_iso),
            })


def report_hours(items: list[BulletinItem]) -> None:
    ok = sum(1 for i in items if i.hour is not None)
    print(f"\nHour parsed (0-23) for {ok} / {len(items)} items.")
    bad = [i for i in items if i.hour is None]
    if bad:
        print(f"FLAGGED {len(bad)} items without a usable hour (stored empty, not 0):")
        for i in bad[:20]:
            print(f"  [{i.hour_flag}] {i.date_iso} {i.title}: {os.path.basename(i.audio_url)}")
        if len(bad) > 20:
            print(f"  ... and {len(bad) - 20} more (see hour_flag column in the listing CSV)")


# ---------------------------------------------------------------------------
# Deterministic day sampling
# ---------------------------------------------------------------------------

def load_sample_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def select_sample_days(days: list[str], cfg: dict) -> list[str]:
    rule = cfg.get("rule", "every_nth_day")
    if rule == "every_nth_day":
        n = int(cfg["n"])
        offset = int(cfg.get("start_offset_days", 0))
        return days[offset::n]
    if rule == "random_days":
        rng = random.Random(int(cfg["seed"]))
        k = min(int(cfg["k"]), len(days))
        return sorted(rng.sample(days, k))
    raise ValueError(f"Unknown sampling rule: {rule}")


def safe_name(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return cleaned.strip("_") or "bulletin"


def download_audio(
    session: requests.Session,
    url: str,
    dest_path: str,
    timeout: int,
    max_retries: int,
    min_delay: float,
    max_delay: float,
) -> None:
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return

    rotate_user_agent(session)
    for attempt in range(1, max_retries + 1):
        try:
            with session.get(url, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                part_path = dest_path + ".part"  # an interrupted download never looks complete
                with open(part_path, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                os.replace(part_path, dest_path)
            return
        except requests.RequestException:
            if attempt >= max_retries:
                raise
            sleep_jitter(min_delay, max_delay)


def strip_overlap(prev_text: str, curr_text: str, min_overlap: int = 80) -> str:
    if not prev_text or not curr_text:
        return curr_text

    prev_norm = " ".join(prev_text.split())
    curr_norm = " ".join(curr_text.split())
    max_scan = min(len(prev_norm), len(curr_norm), 2000)

    for size in range(max_scan, min_overlap - 1, -1):
        if prev_norm[-size:] == curr_norm[:size]:
            trimmed = curr_norm[size:].lstrip()
            return trimmed

    return curr_text


# ---------------------------------------------------------------------------
# Transcription (Whisper). The model is loaded ONCE per run and cached.
# ---------------------------------------------------------------------------

_MODEL_CACHE: dict = {}
MODEL_LOADS = 0  # how many times a model was actually loaded in this process


def _cuda_available(transcriber: str) -> bool:
    try:
        if transcriber == "faster-whisper":
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def resolve_device(transcriber: str, device: str = "auto",
                   compute_type: Optional[str] = None) -> Tuple[str, str]:
    """Pick (device, compute_type). auto = cuda + float16 if a GPU is usable, else cpu + int8."""
    cuda_ok = _cuda_available(transcriber)
    if device == "auto":
        device = "cuda" if cuda_ok else "cpu"
    elif device == "cuda" and not cuda_ok:
        raise RuntimeError(
            "--device cuda was requested but no usable CUDA GPU was found "
            f"(checked via {'ctranslate2' if transcriber == 'faster-whisper' else 'torch'}). "
            "Use --device auto or --device cpu."
        )
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"
    if transcriber == "faster-whisper":
        import ctranslate2
        supported = ctranslate2.get_supported_compute_types(device)
        if compute_type not in supported:
            raise RuntimeError(
                f"compute type '{compute_type}' is not supported on {device}; supported: {sorted(supported)}"
            )
    return device, compute_type


def get_transcriber(transcriber: str, model_name: str, device: str, compute_type: str):
    """Return the cached model, loading it only the first time."""
    global MODEL_LOADS
    key = (transcriber, model_name, device, compute_type)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    start = time.time()
    if transcriber == "faster-whisper":
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed") from exc
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    elif transcriber == "whisper":
        try:
            import whisper
        except ImportError as exc:
            raise RuntimeError("openai-whisper is not installed") from exc
        model = whisper.load_model(model_name, device=device)
    else:
        raise RuntimeError(f"Unknown transcriber: {transcriber}")
    MODEL_LOADS += 1
    print(f"Whisper model loaded (load #{MODEL_LOADS}) in {time.time() - start:.1f} s")
    _MODEL_CACHE[key] = model
    return model


def audio_duration_seconds(path: str) -> Optional[float]:
    """Real audio duration via ffprobe, or None if ffprobe is unavailable or fails."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        return round(float(out), 2)
    except Exception:
        return None


def transcribe_with_stats(
    audio_path: str,
    transcriber: str,
    model_name: str,
    device: str,
    compute_type: str,
) -> dict:
    """Transcribe one file. Returns text, duration_s, seconds (wall time) and rtf (seconds / duration).

    VAD is left at faster-whisper's default (off), exactly as before.
    """
    model = get_transcriber(transcriber, model_name, device, compute_type)
    start = time.time()
    duration = None
    if transcriber == "faster-whisper":
        segments, info = model.transcribe(audio_path)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        duration = round(float(info.duration), 2)
    else:
        result = model.transcribe(audio_path)
        text = (result.get("text") or "").strip()
    seconds = time.time() - start
    if duration is None:
        duration = audio_duration_seconds(audio_path)
    rtf = round(seconds / duration, 4) if duration else None
    return {"text": text, "duration_s": duration, "seconds": round(seconds, 2), "rtf": rtf}


def transcribe_audio(
    audio_path: str,
    transcriber: str,
    model_name: str,
    device: str,
    compute_type: Optional[str] = None,
) -> str:
    """Backward-compatible wrapper: returns only the text (model still loaded once)."""
    device, compute_type = resolve_device(transcriber, device, compute_type)
    return transcribe_with_stats(audio_path, transcriber, model_name, device, compute_type)["text"]


def parse_month_arg(month_arg: str) -> tuple[str, str]:
    parts = month_arg.split("-")
    if len(parts) != 2:
        raise ValueError("month must be in YYYY-MM format")
    year = int(parts[0])
    month = int(parts[1])
    last_day = calendar.monthrange(year, month)[1]
    start = dt.date(year, month, 1).isoformat()
    end = dt.date(year, month, last_day).isoformat()
    return start, end


def load_existing_urls(csv_path: str) -> set[str]:
    if not os.path.exists(csv_path):
        return set()
    urls = set()
    with open(csv_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            url = (row.get("audio_url") or "").strip()
            if url:
                urls.add(url)
    return urls


CSV_FIELDS = [
    "title",
    "date",
    "language",
    "category",
    "audio_url",
    "audio_file",
    "transcript_file",
    "sha256",
    "downloaded_at",
    # added in S2; rows from older callers (e.g. live ingest) leave them empty
    "duration_s",
    "transcriber",
    "whisper_model",
    "device",
    "compute_type",
    "transcribe_seconds",
    "rtf",
    "split",  # train / val / test from the sample plan (whole days)
]


def write_csv_rows(csv_path: str, rows: Iterable[dict]) -> None:
    """Append rows. A NEW file gets the full header; an EXISTING file keeps its own header
    (extra keys are dropped), so older CSVs such as output/metadata.csv are never misaligned."""
    fieldnames = CSV_FIELDS
    exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    if exists:
        with open(csv_path, "r", newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), None)
        if header:
            fieldnames = header
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def resolve_category(options: list[tuple[str, str]], user_value: str) -> str:
    """Map a slug or label to a category slug. 'all' (or empty) means every category."""
    if user_value.strip().lower() in ("", "all"):
        return ""
    values = {value: label for value, label in options}
    if user_value in values:
        return user_value
    lowered = user_value.strip().lower()
    for value, label in options:
        if lowered == label.lower():
            return value
    for value, label in options:
        if lowered in label.lower():
            return value
    raise ValueError("Category not found. Use --list-categories to see options.")


def sort_key(item: BulletinItem) -> tuple:
    date_key = item.date_iso or "0000-00-00"
    time_key = item.time_hint if item.time_hint is not None else 9999
    return (date_key, time_key, item.audio_url)


def announce_transcriber(args) -> None:
    """Resolve device + compute type, print them with the model size, and load the model once."""
    args.device_resolved, args.compute_type_resolved = resolve_device(
        args.transcriber, args.device, args.compute_type)
    print(f"Transcriber: {args.transcriber} | model size: {args.model} | "
          f"device: {args.device_resolved} | compute type: {args.compute_type_resolved}")
    get_transcriber(args.transcriber, args.model, args.device_resolved, args.compute_type_resolved)


def transcribe_to_file(audio_path: str, transcript_path: str, args, prev_text: str = "") -> tuple[str, dict]:
    """Transcribe unless a non-empty transcript already exists (resumable).
    Returns (text, stats); stats is empty when the file was skipped."""
    if os.path.isfile(transcript_path) and os.path.getsize(transcript_path) > 0:
        with open(transcript_path, "r", encoding="utf-8") as handle:
            text = handle.read()
        print(f"skip (transcript exists): {os.path.basename(audio_path)}")
        return text, {}
    res = transcribe_with_stats(audio_path, args.transcriber, args.model,
                                args.device_resolved, args.compute_type_resolved)
    text = res["text"]
    if args.dedupe:
        text = strip_overlap(prev_text, text)
    if text:
        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
        with open(transcript_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    dur = res["duration_s"]
    print(f"transcribed {os.path.basename(audio_path)}: audio "
          f"{'?' if dur is None else f'{dur / 60:.2f} min'}, {res['seconds']:.1f} s, "
          f"real-time factor {res['rtf'] if res['rtf'] is not None else '?'}")
    return text, {"duration_s": dur, "transcribe_seconds": res["seconds"], "rtf": res["rtf"]}


def transcribe_meta(args, stats: dict) -> dict:
    """CSV columns describing how a transcript was made (empty when none was made now)."""
    if not stats:
        return {}
    return {
        "transcriber": args.transcriber,
        "whisper_model": args.model,
        "device": args.device_resolved,
        "compute_type": args.compute_type_resolved,
        "transcribe_seconds": stats.get("transcribe_seconds", ""),
        "rtf": "" if stats.get("rtf") is None else stats["rtf"],
    }


def run_transcribe_only(args) -> int:
    """Transcribe audio already listed in --csv (no network, no download). Resumable: files whose
    transcript exists and is non-empty are skipped. The CSV is rewritten with the S2 columns."""
    if not os.path.isfile(args.csv):
        print(f"CSV not found: {args.csv}")
        return 1
    with open(args.csv, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        header = list(reader.fieldnames or [])
    announce_transcriber(args)
    wall_start = time.time()
    prev_text = ""
    done = skipped = 0
    failed: list[str] = []
    audio_s = trans_s = 0.0
    fieldnames = header + [f for f in CSV_FIELDS if f not in header]

    def save_rows() -> None:
        tmp = args.csv + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, args.csv)

    for n, row in enumerate(rows, 1):
        audio_path = os.path.join(args.out_dir, row.get("audio_file", ""))
        if not os.path.isfile(audio_path):
            print(f"audio missing, skipping: {audio_path}")
            continue
        transcript_path = os.path.join(
            args.out_dir, "text", row.get("date") or "unknown_date",
            safe_name(os.path.splitext(os.path.basename(audio_path))[0]) + ".txt")
        try:
            prev_text, stats = transcribe_to_file(audio_path, transcript_path, args, prev_text)
        except Exception as err:  # keep going; the file is retried on the next run
            print(f"FAILED transcription {audio_path}: {err}")
            failed.append(audio_path)
            continue
        duration = audio_duration_seconds(audio_path)
        if duration is None:
            duration = stats.get("duration_s")
        if duration is not None:
            row["duration_s"] = duration
        if os.path.isfile(transcript_path) and os.path.getsize(transcript_path) > 0:
            row["transcript_file"] = os.path.relpath(transcript_path, args.out_dir)
        if stats:
            row.update(transcribe_meta(args, stats))
            done += 1
            audio_s += stats.get("duration_s") or 0
            trans_s += stats.get("transcribe_seconds") or 0
        else:
            skipped += 1
        save_rows()  # progress survives an interruption
        if n % 20 == 0:
            print(f"progress: {n}/{len(rows)} files processed ({done} transcribed, {skipped} skipped, "
                  f"{len(failed)} failed), {time.time() - wall_start:.0f} s elapsed")
    save_rows()
    if failed:
        print(f"{len(failed)} transcriptions FAILED (re-run to retry): {failed[:5]}")
    wall = time.time() - wall_start
    print(f"\nSummary: {done} transcribed, {skipped} skipped | model loads this run: {MODEL_LOADS} | "
          f"audio {audio_s / 60:.2f} min | transcription {trans_s:.1f} s | "
          f"wall time (incl. model load) {wall:.1f} s | "
          f"real-time factor {round(trans_s / audio_s, 4) if audio_s else 'n/a'}")
    return 0


def download_items(session: requests.Session, items: list[BulletinItem], args, category: str,
                   limit: Optional[int] = None) -> int:
    """Download (and optionally transcribe) items, writing one CSV row each. Returns saved count."""
    existing_urls = load_existing_urls(args.csv)
    saved_count = 0
    prev_text = ""
    failures: list[dict] = []
    args.download_failures = failures
    for item in sorted(items, key=sort_key):
        if limit is not None and saved_count >= limit:
            print(f"Reached --limit {limit}; stopping downloads.")
            break
        if item.audio_url in existing_urls:
            continue

        date_folder = item.date_iso or "unknown_date"
        audio_name = safe_name(os.path.splitext(os.path.basename(item.audio_url))[0]) + ".mp3"
        audio_path = os.path.join(args.out_dir, "audio", date_folder, audio_name)

        try:
            download_audio(
                session,
                item.audio_url,
                audio_path,
                args.timeout,
                args.max_retries,
                args.min_delay,
                args.max_delay,
            )
        except (requests.RequestException, OSError) as err:
            failures.append({"audio_url": item.audio_url, "date": item.date_iso, "error": str(err)})
            print(f"FAILED {item.audio_url}: {err}")
            sleep_jitter(args.min_delay, args.max_delay)
            continue

        transcript_path = ""
        stats: dict = {}
        if args.transcribe:
            transcript_name = safe_name(os.path.splitext(audio_name)[0]) + ".txt"
            transcript_path = os.path.join(args.out_dir, "text", date_folder, transcript_name)
            prev_text, stats = transcribe_to_file(audio_path, transcript_path, args, prev_text)
            if not (os.path.isfile(transcript_path) and os.path.getsize(transcript_path) > 0):
                transcript_path = ""

        duration = audio_duration_seconds(audio_path)
        if duration is None:
            duration = stats.get("duration_s")
        file_hash = sha256_file(audio_path)
        row = {
            "title": item.title,
            "date": item.date_iso or item.date_text,
            "language": args.language,
            "category": category or "all",
            "audio_url": item.audio_url,
            "audio_file": os.path.relpath(audio_path, args.out_dir),
            "transcript_file": os.path.relpath(transcript_path, args.out_dir)
            if transcript_path
            else "",
            "sha256": file_hash,
            "downloaded_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "duration_s": "" if duration is None else duration,
            "split": getattr(args, "day_split", {}).get(item.date_iso, ""),
            **transcribe_meta(args, stats),
        }
        # Write immediately to CSV after each item is processed
        write_csv_rows(args.csv, [row])
        existing_urls.add(item.audio_url)
        saved_count += 1
        print(f"downloaded {audio_path} ({os.path.getsize(audio_path)} bytes, sha256 {file_hash[:12]}...)")

        sleep_jitter(args.min_delay, args.max_delay)
    if failures:
        fail_path = os.path.join(os.path.dirname(args.csv) or ".", "download_failures.json")
        with open(fail_path, "w", encoding="utf-8") as handle:
            json.dump(failures, handle, indent=2, ensure_ascii=False)
        print(f"{len(failures)} downloads FAILED; listed in {fail_path}. Re-run the same command to retry them.")
    return saved_count


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Hindi titles on Windows consoles

    parser = argparse.ArgumentParser(description="Scrape AIR main audio bulletins.")
    parser.add_argument("--language", default="english", help="english|hindi|urdu")
    parser.add_argument("--category", default="hourly-news",
                        help="Category slug or label; 'all' = every category")
    parser.add_argument("--from", dest="date_from",
                        help="First day YYYY-MM-DD (inclusive; the site's own bounds are exclusive, handled internally)")
    parser.add_argument("--to", dest="date_to", help="Last day YYYY-MM-DD (inclusive)")
    parser.add_argument("--month", help="Month in YYYY-MM format")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    parser.add_argument("--csv", default="output/metadata.csv", help="CSV path")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Min delay between requests")
    parser.add_argument("--max-delay", type=float, default=3.0, help="Max delay between requests")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    parser.add_argument("--max-retries", type=int, default=3, help="Retry count")
    parser.add_argument("--max-pages", type=int, default=200, help="Max pagination pages per window")
    parser.add_argument("--list-categories", action="store_true", help="List categories and exit")
    parser.add_argument("--transcribe", action="store_true", help="Transcribe audio to text")
    parser.add_argument("--transcriber", default="faster-whisper", help="faster-whisper|whisper")
    parser.add_argument("--model", default="base", help="Whisper model size: tiny|base|small|medium (or any name the engine accepts)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"],
                        help="auto = cuda if a GPU is usable, else cpu")
    parser.add_argument("--compute-type", default=None,
                        help="faster-whisper compute type, e.g. float16|int8|int8_float16|float32 "
                             "(default: float16 on cuda, int8 on cpu)")
    parser.add_argument("--transcribe-only", action="store_true",
                        help="Transcribe audio already listed in --csv (relative to --out-dir); "
                             "no network, no download; skips files that already have a transcript")
    parser.add_argument("--dedupe", action="store_true", help="Remove overlap vs previous bulletin")
    parser.add_argument("--user-agent", default=DEFAULT_UA, help="HTTP user agent")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Crawl listings and write a listing CSV; no audio download, no Whisper")
    parser.add_argument("--listing-csv", default=os.path.join("data", "listing_metadata.csv"),
                        help="Where --metadata-only writes its CSV")
    parser.add_argument("--window-days", type=int, default=7, help="Days per query window")
    parser.add_argument("--sample", action="store_true",
                        help="Download ALL bulletins of days chosen by the rule in --sample-config")
    parser.add_argument("--sample-config", default=os.path.join("config", "sample_config.json"))
    parser.add_argument("--sample-option", default="A", choices=["A", "rule"],
                        help="A = the explicit day list of option A in the config (pilot_plan_s4; days are "
                             "NEVER re-drawn from the seed); rule = legacy every_nth_day/random_days rule")
    parser.add_argument("--plan-out", default=os.path.join("data", "sample_plan.json"),
                        help="Where --sample saves the rule, seed, chosen days and counts")
    parser.add_argument("--limit", type=int, default=None, help="Download at most N files (testing)")
    parser.add_argument("--yes", action="store_true", help="Skip the --sample confirmation prompt")
    args = parser.parse_args()

    if args.transcribe_only:
        try:
            return run_transcribe_only(args)
        except RuntimeError as err:
            print(f"ERROR: {err}")
            return 1

    if args.transcribe:
        try:
            announce_transcriber(args)
        except RuntimeError as err:
            print(f"ERROR: {err}")
            return 1

    explicit_days: Optional[list[str]] = None
    args.day_split = {}
    sample_cfg: dict = {}
    if args.sample and args.sample_option == "A":
        sample_cfg = load_sample_config(args.sample_config)
        option = sample_cfg["pilot_plan_s4"]["option_A_about_10_days"]
        explicit_days = list(option["days"])
        args.day_split = {d: name for name, info in option["split"].items() for d in info["days"]}
        date_from, date_to = min(explicit_days), max(explicit_days)
    elif args.month:
        date_from, date_to = parse_month_arg(args.month)
    else:
        if not args.date_from or not args.date_to:
            parser.error("Provide --from and --to or --month")
        date_from = args.date_from
        date_to = args.date_to
    first_day = dt.date.fromisoformat(date_from)
    last_day = dt.date.fromisoformat(date_to)
    if last_day < first_day:
        parser.error("--to must not be before --from")

    session = make_session(args.user_agent)
    if not check_robots_txt(session):
        return 2

    categories = fetch_categories(
        session,
        args.language,
        args.timeout,
        args.max_retries,
        args.min_delay,
        args.max_delay,
    )

    if args.list_categories:
        for value, label in categories:
            print(f"{value}\t{label}")
        return 0

    category = resolve_category(categories, args.category)

    # ---- choose the windows to crawl
    chosen_days: list[str] = []
    if args.sample:
        if explicit_days is not None:
            chosen_days = explicit_days  # source of truth: the config's explicit list
        else:
            sample_cfg = load_sample_config(args.sample_config)
            all_days = [(first_day + dt.timedelta(days=i)).isoformat()
                        for i in range((last_day - first_day).days + 1)]
            chosen_days = select_sample_days(all_days, sample_cfg)
        if not chosen_days:
            print("The sampling rule selected no days for this range.")
            return 0
        windows = []
        for d in chosen_days:
            day = dt.date.fromisoformat(d)
            windows.extend(make_windows(day, day, 1))
    else:
        windows = make_windows(first_day, last_day, args.window_days)

    bulletins = crawl_windows(
        session, windows, args.language, category, args.timeout, args.max_retries,
        args.min_delay, args.max_delay, args.max_pages,
    )

    # ---- metadata only
    if args.metadata_only:
        report_day_counts(bulletins, first_day, last_day)
        report_hours(bulletins)
        write_listing_csv(args.listing_csv, bulletins, args.language, category, windows)
        print(f"\nWrote {len(bulletins)} rows to {args.listing_csv} (no audio downloaded, no Whisper).")
        return 0

    if not bulletins:
        print("No bulletins found for the given range.")
        return 0

    # ---- sample: show the plan, confirm, then download
    if args.sample:
        per_day = {d: sum(1 for b in bulletins if b.date_iso == d) for d in chosen_days}
        known = [estimate_minutes(b.audio_url) for b in bulletins]
        known_minutes = sum(m for m in known if m is not None)
        unknown = sum(1 for m in known if m is None)
        print("\n=== SAMPLE PLAN ===")
        if explicit_days is not None:
            print(f"source: explicit day list, option A, {args.sample_config} (pilot_plan_s4); seed not used to draw days")
            rule_info = {"source": "explicit option A day list", "config": args.sample_config,
                         "split": args.day_split}
        else:
            print("rule:", json.dumps({k: v for k, v in sample_cfg.items() if k not in ("notes", "pilot_plan_s4")}))
            rule_info = {k: v for k, v in sample_cfg.items() if k != "pilot_plan_s4"}
        print("chosen days:", ", ".join(chosen_days))
        for d, n in per_day.items():
            print(f"  {d}: {n} items")
        print(f"total items: {len(bulletins)}")
        print(f"estimated audio: {known_minutes} min from filenames with an HHMM-HHMM pattern; "
              f"{unknown} items have no duration estimate (so the real total is larger)")
        n_hourly = sum(1 for b in bulletins if b.title == "Hourly News")
        n_other = len(bulletins) - n_hourly
        est_total = n_hourly * 4.74 + n_other * 15
        print(f"estimated total audio: {est_total:.0f} min ({est_total / 60:.1f} h) = {n_hourly} hourly x 4.74 min "
              f"(measured on 2 files) + {n_other} other x 15 min (UNMEASURED assumption)")
        if args.limit is not None:
            print(f"--limit {args.limit}: only the first {args.limit} files will be downloaded")
        plan = {
            "rule": rule_info,
            "seed": sample_cfg.get("seed"),
            "range": [date_from, date_to],
            "language": args.language,
            "category": category or "all",
            "chosen_days": chosen_days,
            "items_per_day": per_day,
            "total_items": len(bulletins),
            "estimated_known_minutes": known_minutes,
            "items_without_duration_estimate": unknown,
            "limit": args.limit,
            "out_dir": args.out_dir,
            "created_utc": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        os.makedirs(os.path.dirname(args.plan_out) or ".", exist_ok=True)
        with open(args.plan_out, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, ensure_ascii=False)
        print(f"plan saved to {args.plan_out}")
        if not args.yes:
            try:
                answer = input("Download these files? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer != "y":
                print("Aborted; nothing downloaded.")
                return 0

    saved_count = download_items(session, bulletins, args, category, limit=args.limit)

    if saved_count > 0:
        print(f"Saved {saved_count} items to {args.csv}")
    else:
        print("No new items to save.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
