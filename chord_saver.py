"""ค้นหาคอร์ดเพลงจาก chordtabs.in.th แล้วเซฟรูปเนื้อเพลง+คอร์ด ตั้งชื่อไฟล์เป็นชื่อเพลง

ใช้งาน:
    python chord_saver.py                 -> เปิดหน้าต่างโปรแกรม (GUI อยู่ใน gui.py)
    python chord_saver.py songs.txt       -> อ่านรายชื่อเพลงจากไฟล์ (บรรทัดละเพลง)
    python chord_saver.py "ฝนตกไหม" "ขอใจเธอแลกเบอร์โทร"
    python chord_saver.py --label songs.txt  -> ใส่ชื่อไฟล์ไว้ที่มุมขวาล่างของรูปด้วย

ต้องติดตั้งก่อน:  pip install playwright   (ใช้ Chrome หรือ Edge ที่มีในเครื่อง)
"""
from __future__ import annotations

import base64
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin

from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

SITE = "https://chordtabs.in.th/"
SONG_URL_RE = re.compile(r"^https?://chordtabs\.in\.th/(\d+)/?(chord-guitar)?$")
SEARCH_TIMEOUT_MS = 20_000
RESULT_SETTLE_MS = 1_200
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')
# ตอนรันเป็น .exe ให้เซฟไว้ข้างไฟล์ exe (ไม่ใช่โฟลเดอร์ชั่วคราวที่ exe แตกไฟล์ออกมา)
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = APP_DIR / "chords"
LABEL_FONT_RATIO = 0.022  # ขนาดตัวอักษรป้ายชื่อ = 2.2% ของความกว้างรูป (620px ≈ 16px, 970px ≈ 21px)
LABEL_MIN_FONT_PX = 16
LABEL_MARGIN_PX = 10
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}

Log = Callable[[str], None]


@dataclass(frozen=True)
class SongHit:
    url: str
    title: str  # เช่น "ฝนตกไหม Three Man Down"


@dataclass(frozen=True)
class SaveResult:
    query: str
    ok: bool
    message: str
    path: Path | None = None


def clean_filename(name: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub(" ", name)
    return re.sub(r"\s+", " ", cleaned).strip(" .") or "song"


def unique_path(folder: Path, stem: str, suffix: str) -> Path:
    candidate = folder / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def parse_song_lines(lines: Iterable[str]) -> list[str]:
    return [s.strip() for s in lines if s.strip() and not s.strip().startswith("#")]


def _title_from_result(text: str) -> str:
    text = re.sub(r"\s*-\s*Chordtabs\s*$", "", text.strip())
    return re.sub(r"^คอร์ด(เพลง)?\s*", "", text).strip()


def find_song(page: Page, query: str) -> SongHit | None:
    """ค้นหาผ่านช่องค้นหาของเว็บ แล้วเลือกผลลัพธ์ "คอร์ด" อันแรก"""
    if SONG_URL_RE.match(query):
        return SongHit(url=query, title="")
    page.goto(SITE, wait_until="domcontentloaded")
    page.wait_for_selector("input.gsc-input", timeout=SEARCH_TIMEOUT_MS)
    page.fill("input.gsc-input", query)
    page.keyboard.press("Enter")
    try:
        page.wait_for_selector("a.gs-title", timeout=SEARCH_TIMEOUT_MS)
    except PlaywrightTimeout:
        return None
    page.wait_for_timeout(RESULT_SETTLE_MS)
    for link in page.query_selector_all("a.gs-title"):
        href = (link.get_attribute("href") or "").strip()
        if SONG_URL_RE.match(href):
            return SongHit(url=href, title=_title_from_result(link.inner_text()))
    return None


def download_chord_image(page: Page, hit: SongHit) -> tuple[bytes, str, str]:
    """เปิดหน้าเพลง แล้วดึงรูปเนื้อเพลง+คอร์ด (img.img) คืนค่า (bytes, นามสกุล, ชื่อเพลงจากเว็บ)"""
    page.goto(hit.url, wait_until="domcontentloaded")
    img = page.wait_for_selector("#divlyric img.img, img.img", timeout=SEARCH_TIMEOUT_MS)
    src = img.get_attribute("src") or ""
    if not src:
        raise RuntimeError("ไม่พบรูปคอร์ดในหน้าเพลง")
    image_url = urljoin(page.url, src)
    alt_title = _title_from_result(img.get_attribute("alt") or "")
    response = page.request.get(image_url, headers={"Referer": hit.url})
    if not response.ok:
        raise RuntimeError(f"โหลดรูปไม่สำเร็จ (HTTP {response.status})")
    suffix = Path(src.split("?")[0]).suffix or ".png"
    return response.body(), suffix, hit.title or alt_title


def add_name_label(page: Page, data: bytes, suffix: str, text: str) -> bytes:
    """วาดชื่อไฟล์ที่มุมขวาล่างของรูป (ใช้เบราว์เซอร์วาด เพื่อให้สระ/วรรณยุกต์ไทยถูกต้อง) คืนค่าเป็น PNG"""
    mime = IMAGE_MIME.get(suffix.lower(), "image/png")
    src = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    page.set_content(
        f"""<html><body style="margin:0">
        <div id="wrap" style="position:relative;display:inline-block;line-height:0">
          <img id="pic" src="{src}" style="display:block">
          <div id="label" style="position:absolute;right:{LABEL_MARGIN_PX}px;bottom:{LABEL_MARGIN_PX}px;
               font-family:Tahoma,'Leelawadee UI',sans-serif;line-height:1.4;color:#222;
               background:rgba(255,255,255,0.85);padding:2px 8px;border-radius:4px;
               white-space:nowrap">{html.escape(text)}</div>
        </div></body></html>"""
    )
    page.wait_for_function("document.getElementById('pic').complete")
    width = page.evaluate("document.getElementById('pic').naturalWidth")
    font_px = max(LABEL_MIN_FONT_PX, round(width * LABEL_FONT_RATIO))
    page.evaluate(f"document.getElementById('label').style.fontSize = '{font_px}px'")
    return page.locator("#wrap").screenshot(type="png")


def save_song(page: Page, query: str, out_dir: Path, use_web_title: bool, add_label: bool = False) -> SaveResult:
    try:
        hit = find_song(page, query)
        if hit is None:
            return SaveResult(query, False, "ไม่พบเพลงนี้ในเว็บ")
        data, suffix, web_title = download_chord_image(page, hit)
        prefer_web_title = use_web_title or bool(SONG_URL_RE.match(query))
        name = web_title if (prefer_web_title and web_title) else query
        if add_label:
            suffix = ".png"
        path = unique_path(out_dir, clean_filename(name), suffix)
        if add_label:
            data = add_name_label(page, data, suffix, clean_filename(name))
        path.write_bytes(data)
        return SaveResult(query, True, f"{hit.url} -> {path.name}", path)
    except PlaywrightTimeout:
        return SaveResult(query, False, "เว็บตอบช้าเกินไป (timeout) ลองใหม่อีกครั้ง")
    except Exception as exc:  # noqa: BLE001 - รายงานทุกข้อผิดพลาดต่อเพลง แล้วทำเพลงถัดไป
        return SaveResult(query, False, f"ผิดพลาด: {exc}")


def launch_browser(p, show_browser: bool) -> Browser:
    last_error: Exception | None = None
    for channel in ("chrome", "msedge", None):
        try:
            kwargs = {"headless": not show_browser}
            if channel:
                kwargs["channel"] = channel
            return p.chromium.launch(**kwargs)
        except Exception as exc:  # noqa: BLE001 - ลองเบราว์เซอร์ตัวถัดไป
            last_error = exc
    raise RuntimeError(
        "เปิดเบราว์เซอร์ไม่ได้ ติดตั้ง Chrome/Edge หรือรัน: python -m playwright install chromium"
    ) from last_error


def run_batch(
    songs: list[str],
    out_dir: Path,
    log: Log = print,
    use_web_title: bool = False,
    show_browser: bool = False,
    add_label: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[SaveResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[SaveResult] = []
    with sync_playwright() as p:
        browser = launch_browser(p, show_browser)
        page = browser.new_page(locale="th-TH", device_scale_factor=1)
        for i, song in enumerate(songs, 1):
            log(f"[{i}/{len(songs)}] กำลังค้นหา: {song}")
            result = save_song(page, song, out_dir, use_web_title, add_label)
            results.append(result)
            log(("   ✔ " if result.ok else "   ✘ ") + result.message)
            if on_progress:
                on_progress(i, len(songs))
        browser.close()
    ok = sum(r.ok for r in results)
    log(f"\nเสร็จแล้ว: สำเร็จ {ok}/{len(results)} เพลง  -> {out_dir}")
    failed = [r.query for r in results if not r.ok]
    if failed:
        log("ไม่สำเร็จ: " + ", ".join(failed))
    return results


def main(argv: list[str]) -> None:
    add_label = "--label" in argv
    argv = [a for a in argv if a != "--label"]
    if not argv:
        from gui import run_gui

        run_gui()
        return
    first = Path(argv[0])
    if len(argv) == 1 and first.suffix.lower() == ".txt" and first.exists():
        songs = parse_song_lines(first.read_text(encoding="utf-8-sig").splitlines())
    else:
        songs = parse_song_lines(argv)
    log: Log = print if sys.stdout else (lambda _msg: None)  # exe แบบไม่มีหน้าต่างคอนโซล
    run_batch(songs, DEFAULT_OUTPUT_DIR, log, add_label=add_label)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
