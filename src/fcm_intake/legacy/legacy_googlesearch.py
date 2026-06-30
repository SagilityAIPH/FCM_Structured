import json
import os
import re
import time
import threading
import random
import traceback
import queue
import tkinter as tk
from tkinter import messagebox
from difflib import SequenceMatcher
from typing import Callable
 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from edge_auto import build_edge_service, find_msedge_path
from fcm_intake.config import EDGE_DRIVER_PATH as CONFIG_EDGE_DRIVER_PATH
 
# ============================================================
# OUTPUT VARIABLES (filled when "Copy Address" is pressed)
# ============================================================
providerName = ""
providerAddr = ""
providerCity = ""
providerState = ""
providerZip = ""
providerPhone = ""
 
# =========================
# CONFIG (edit as needed)
# =========================
EDGE_DRIVER_PATH = CONFIG_EDGE_DRIVER_PATH  # fallback only
 
PROFILE_DIR = os.path.join(os.path.dirname(__file__), "edge_profile_google")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "google_cache.json")
 
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days
 
# pacing (helps reduce CAPTCHA triggers)
BASE_INTERVAL_SECONDS = 60
JITTER_SECONDS = 15
 
# backoff when blocked
BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 30 * 60
 
HEADLESS = False  # Google blocks headless more often
 
# Google XPaths (fallback)
GOOGLE_TEXTBOX_XPATH = "/html/body/div[2]/div[4]/form/div[1]/div[1]/div[1]/div[1]/div[3]/textarea"
GOOGLE_SEARCHBTN_XPATH = "/html/body/div[2]/div[4]/form/div[1]/div[1]/div[2]/div[4]/div[6]/center/input[1]"
 
TOP_N_ALWAYS = 5  # always show top 5 results (radio)
 
 
# =========================
# CACHE
# =========================
def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}
 
 
def save_cache(cache: dict) -> None:
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
 
 
def norm_key(s: str) -> str:
    return " ".join((s or "").strip().lower().split())
 
 
# =========================
# REGEX + HELPERS
# =========================
PHONE_RE = re.compile(r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")
 
US_ADDR_STRICT = re.compile(
    r"\b(\d{1,6}\s+[A-Za-z0-9#.\-'\s]+?),\s*([A-Za-z.\-'\s]+?),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)\b"
)
 
US_ADDR_LOOSE = re.compile(
    r"\b("
    r"\d{1,6}\s+[A-Za-z0-9#.\-'\s]{2,80}"
    r"(?:,\s*|\s+)"
    r"[A-Za-z.\-'\s]{2,60}"
    r"(?:,\s*|\s+)"
    r"[A-Z]{2}"
    r"(?:\s+\d{5}(?:-\d{4})?)?"
    r")\b"
)
 
CITY_STATE_ZIP = re.compile(r"\b([A-Za-z.\-'\s]{2,60}),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?\b")
 
 
def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())
 
 
def clean_provider_name(name: str) -> str:
    name = _clean(name)
    name = re.sub(r"\s+\|\s+.*$", "", name)
    name = re.sub(r"\s+-\s+Updated.*$", "", name, flags=re.I)
    name = re.sub(r"^(Address|Phone|Hours)\s*:\s*", "", name, flags=re.I)
    return name.strip()
 
 
def normalize_phone(s: str) -> str:
    s = (s or "").strip()
    m = PHONE_RE.search(s)
    if not m:
        return s
    digits = re.sub(r"\D+", "", m.group(0))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1 {digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    return m.group(0).strip()
 
 
def parse_us_address(addr: str) -> dict:
    """
    Returns:
      Address Line 1, City, State, Zip
    """
    raw = _clean(addr)
    raw = re.sub(r"(?i)^\s*address\s*:\s*", "", raw).strip()
    raw = re.sub(r"(?i)(,\s*)?(united states|usa|us)\s*$", "", raw).strip()
    raw = raw.rstrip(",").strip()
 
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    street = city = state = zipc = ""
 
    if len(parts) >= 2:
        last = parts[-1]
        m_last = re.match(r"^(?P<state>[A-Z]{2})(?:\s+(?P<zip>\d{5}(?:-\d{4})?))?\s*$", last)
        if m_last:
            state = (m_last.group("state") or "").upper()
            zipc = (m_last.group("zip") or "").strip()
            city = parts[-2]
            street = ", ".join(parts[:-2]) if len(parts) >= 3 else ""
            if not street and len(parts) == 2:
                street = parts[0]
                city = ""
            return {
                "Address Line 1": _clean(street),
                "City": _clean(city),
                "State": _clean(state),
                "Zip": _clean(zipc),
            }
 
    m = re.match(
        r"^(?P<street>.+?),\s*(?P<city>[^,]+?),\s*(?P<state>[A-Z]{2})(?:\s+(?P<zip>\d{5}(?:-\d{4})?))?\s*$",
        raw
    )
    if m:
        return {
            "Address Line 1": _clean(m.group("street")),
            "City": _clean(m.group("city")),
            "State": _clean(m.group("state")).upper(),
            "Zip": _clean(m.group("zip") or ""),
        }
 
    return {"Address Line 1": raw, "City": "", "State": "", "Zip": ""}
 
 
# =========================
# GOOGLE NAV + EXTRACTION
# =========================
def accept_google_consent_if_any(driver):
    for css in [
        "button#L2AGLb",
        "button[aria-label='Accept all']",
        "div[role='dialog'] button",
    ]:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, css)
            if btns:
                driver.execute_script("arguments[0].click();", btns[0])
                time.sleep(0.7)
                return
        except Exception:
            pass
 
 
def detect_google_block_or_captcha(driver) -> bool:
    try:
        url = (driver.current_url or "").lower()
        src = (driver.page_source or "").lower()
        title = (driver.title or "").lower()
 
        if "/sorry/" in url:
            return True
        if "unusual traffic" in src:
            return True
        if "recaptcha" in src or "captcha" in src:
            return True
        if "sorry" in title and "google" in title:
            return True
    except Exception:
        return False
    return False
 
 
def search_google_serp(driver, query: str, timeout: int = 20):
    driver.get('https://www.google.com/')
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    accept_google_consent_if_any(driver)
 
    wait = WebDriverWait(driver, timeout)
 
    try:
        box = wait.until(EC.presence_of_element_located((By.NAME, "q")))
    except Exception:
        box = wait.until(EC.presence_of_element_located((By.XPATH, GOOGLE_TEXTBOX_XPATH)))
 
    box.clear()
    box.send_keys(query)
 
    try:
        box.send_keys(Keys.ENTER)
    except Exception:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, GOOGLE_SEARCHBTN_XPATH)))
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            box.submit()
 
    time.sleep(0.8)
    if not detect_google_block_or_captcha(driver):
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#search")))
 
 
def extract_provider_name_from_google(driver) -> str:
    """
    Try to extract provider/business name from Google Knowledge Panel first,
    then fall back to top search result title.
    """
    candidates = [
        "#rhs h2[data-attrid='title']",
        "#rhs div[data-attrid='title'] span",
        "#rhs div[role='heading']",
        "#rhs h2",
        "[data-attrid='title']",
    ]
 
    for sel in candidates:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                txt = clean_provider_name(el.text)
                if txt and len(txt) > 2:
                    return txt
        except Exception:
            pass
 
    fallback_selectors = [
        "#search h3",
        "h3",
    ]
    for sel in fallback_selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                txt = clean_provider_name(el.text)
                if txt and len(txt) > 2:
                    return txt
        except Exception:
            pass
 
    return ""
 
 
def extract_from_google_knowledge_panel(driver) -> list[dict]:
    results, seen = [], set()
 
    rhs = None
    for sel in ["#rhs", "#kp-wp-tab-overview", "div[data-attrid]"]:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        if els:
            rhs = els[0]
            break
    if not rhs:
        return results
 
    blob = _clean(rhs.text)
    if not blob:
        return results
 
    provider_name = extract_provider_name_from_google(driver)
 
    addr_candidates = []
    selectors = [
        "#rhs span.LrzXr",
        "#rhs [data-attrid*='address']",
        "#rhs [data-attrid*='location']",
        "#rhs [data-attrid*='kc:/location/location:address']",
    ]
    for sel in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            t = _clean(el.text)
            if t and (US_ADDR_LOOSE.search(t) or CITY_STATE_ZIP.search(t) or re.search(r"\b[A-Z]{2}\b", t)):
                addr_candidates.append(t)
 
    if not addr_candidates:
        addr_candidates += [_clean(m.group(0)) for m in US_ADDR_STRICT.finditer(blob)]
        addr_candidates += [_clean(m.group(0)) for m in US_ADDR_LOOSE.finditer(blob)]
        if not addr_candidates:
            addr_candidates += [_clean(m.group(0)) for m in CITY_STATE_ZIP.finditer(blob)]
 
    phone = ""
    mph = PHONE_RE.search(blob)
    if mph:
        phone = _clean(mph.group(0))
 
    for addr in addr_candidates[:10]:
        key = (provider_name, addr, phone)
        if key not in seen:
            seen.add(key)
            results.append({
                "providerName": provider_name,
                "address": addr,
                "phone": phone,
                "src": "kp",
            })
    return results
 
 
def extract_from_google_ai_overview(driver) -> list[dict]:
    try:
        body_text = _clean(driver.find_element(By.TAG_NAME, "body").text)
    except Exception:
        return []
 
    m_addr = re.search(r"(?im)^\s*Address:\s*(.+?)\s*$", body_text)
    m_csz = re.search(r"(?im)^\s*City/State/Zip:\s*(.+?)\s*$", body_text)
 
    if not (m_addr and m_csz):
        return []
 
    full_addr = f"{_clean(m_addr.group(1))}, {_clean(m_csz.group(1))}"
 
    phone = ""
    mph = PHONE_RE.search(body_text)
    if mph:
        phone = _clean(mph.group(0))
 
    provider_name = extract_provider_name_from_google(driver)
 
    return [{
        "providerName": provider_name,
        "address": full_addr,
        "phone": phone,
        "src": "ai",
    }]
 
 
def extract_addresses_from_google_snippets(driver) -> list[dict]:
    results, seen = [], set()
    blocks = driver.find_elements(By.CSS_SELECTOR, "#search .MjjYud, #search .g, #search div[data-snhf]")
    if not blocks:
        blocks = driver.find_elements(By.CSS_SELECTOR, "#search")
 
    for b in blocks:
        txt = _clean(b.text)
        if not txt:
            continue
 
        provider_name = ""
        try:
            h3 = b.find_element(By.CSS_SELECTOR, "h3")
            provider_name = clean_provider_name(h3.text)
        except Exception:
            pass
 
        matches = []
        matches += [m.group(0) for m in US_ADDR_STRICT.finditer(txt)]
        matches += [m.group(0) for m in US_ADDR_LOOSE.finditer(txt)]
        if not matches:
            matches += [m.group(0) for m in CITY_STATE_ZIP.finditer(txt)]
        if not matches:
            continue
 
        phone = _clean(PHONE_RE.search(txt).group(0)) if PHONE_RE.search(txt) else ""
        for addr in matches[:3]:
            addr = _clean(addr)
            key = (provider_name, addr, phone)
            if key not in seen:
                seen.add(key)
                results.append({
                    "providerName": provider_name,
                    "address": addr,
                    "phone": phone,
                    "src": "snip",
                })
    return results
 
 
# =========================
# CONFIDENCE (for sorting)
# =========================
def _sim(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()
 
 
def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")
 
 
def norm_phone(s: str) -> str:
    d = _digits_only(s)
    return d[-10:] if len(d) >= 10 else d
 
 
def extract_zip(s: str) -> str:
    m = re.search(r"\b(\d{5})(?:-\d{4})?\b", s or "")
    return m.group(1) if m else ""
 
 
def extract_state(s: str) -> str:
    m = re.search(r"\b([A-Z]{2})\b", (s or "").upper())
    return m.group(1) if m else ""
 
 
def extract_street_number(s: str) -> str:
    m = re.search(r"\b(\d{1,6})\b", s or "")
    return m.group(1) if m else ""
 
 
def clean_street(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\b(suite|ste|unit|fl|floor|bldg|building|room|rm|#)\b\.?", " ", s)
    s = re.sub(r"[^a-z0-9\s\-']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
 
 
def parse_city_state_zip_any(text: str) -> tuple[str, str, str]:
    t = (text or "").strip()
    m = US_ADDR_STRICT.search(t)
    if m:
        return (_clean(m.group(2)), _clean(m.group(3)), _clean(m.group(4)))
    m2 = CITY_STATE_ZIP.search(t)
    if m2:
        return (_clean(m2.group(1)), _clean(m2.group(2)), _clean(m2.group(3) or ""))
    m3 = re.search(r"\b([A-Za-z][A-Za-z .'\-]{2,60})\s+([A-Z]{2})(?:\s+(\d{5})(?:-\d{4})?)?\b", t)
    if m3:
        return (_clean(m3.group(1)), _clean(m3.group(2)), _clean(m3.group(3) or ""))
    return ("", "", "")
 
 
def address_score(result_addr: str, query_addr: str) -> float:
    ra = _clean(result_addr)
    qa = _clean(query_addr)
    if not ra or not qa:
        return 0.0
 
    r_city, r_state, r_zip = parse_city_state_zip_any(ra)
    q_city, q_state, q_zip = parse_city_state_zip_any(qa)
 
    rnum = extract_street_number(ra)
    qnum = extract_street_number(qa)
    num_ok = 1.0 if (rnum and qnum and rnum == qnum) else 0.0
 
    def strip_non_street(s: str) -> str:
        s2 = clean_street(s)
        s2 = re.sub(r"\b\d{1,6}\b", " ", s2)
        s2 = re.sub(r"\b\d{5}(?:-\d{4})?\b", " ", s2)
        s2 = re.sub(r"\b([a-z]{2})\b", " ", s2)
        s2 = re.sub(r"\s+", " ", s2).strip()
        return s2
 
    street_sim = _sim(strip_non_street(ra), strip_non_street(qa))
    city_sim = _sim(q_city, r_city) if (q_city and r_city) else 0.0
 
    state_ok = 0.0
    if q_state:
        state_ok = 1.0 if (extract_state(r_state) and extract_state(r_state) == extract_state(q_state)) else 0.0
 
    zip_ok = 0.0
    if q_zip:
        zip_ok = 1.0 if (extract_zip(r_zip) and extract_zip(r_zip) == extract_zip(q_zip)) else 0.0
 
    return (0.30 * num_ok + 0.45 * street_sim + 0.15 * city_sim + 0.05 * state_ok + 0.05 * zip_ok)
 
 
def compute_confidence(result_addr: str, result_phone: str, query_text: str) -> int:
    qph = norm_phone(query_text)
    rph = norm_phone(result_phone)
    phone_part = 1.0 if (qph and rph and qph == rph) else 0.0
    addr_part = address_score(result_addr, query_text)
    score = (0.10 * phone_part + 0.90 * addr_part) * 100.0
    return int(round(max(0.0, min(100.0, score))))
 
 
# =========================
# SEARCHER
# =========================
class GoogleSearcher:
    def __init__(self):
        self.driver = None
        self.last_run_ts = 0.0
        self.block_attempt = 0
        self.cooldown_until = 0.0
 
    def _ensure_driver(self):
        if self.driver:
            return

        os.makedirs(PROFILE_DIR, exist_ok=True)
        options = Options()
        options.use_chromium = True
        options.binary_location = find_msedge_path()
        options.add_argument(f"--user-data-dir={PROFILE_DIR}")

        try:
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
        except Exception:
            pass

        if HEADLESS:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")

        service = build_edge_service(EDGE_DRIVER_PATH)
        self.driver = webdriver.Edge(service=service, options=options)

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
 
    def rate_limit(self):
        now = time.time()
        elapsed = now - self.last_run_ts
        target_gap = BASE_INTERVAL_SECONDS + random.uniform(0, JITTER_SECONDS)
        if elapsed < target_gap:
            time.sleep(target_gap - elapsed)
        self.last_run_ts = time.time()
 
    def _apply_block_backoff(self) -> int:
        self.block_attempt += 1
        wait_s = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (self.block_attempt - 1)))
        wait_s += random.uniform(0, 10)
        self.cooldown_until = time.time() + wait_s
        return int(wait_s)
 
    def run_pipeline(self, search_item: str) -> list[dict]:
        self._ensure_driver()
        driver = self.driver
 
        now = time.time()
        if now < self.cooldown_until:
            time.sleep(self.cooldown_until - now)
 
        search_google_serp(driver, search_item + " full address")
        if detect_google_block_or_captcha(driver):
            wait_s = self._apply_block_backoff()
            return [{"_blocked": True, "cooldown_seconds": wait_s}]
 
        self.block_attempt = 0
        self.cooldown_until = 0.0
 
        kp_hits = extract_from_google_knowledge_panel(driver)
        ai_hits = extract_from_google_ai_overview(driver) if not kp_hits else []
        snip_hits = extract_addresses_from_google_snippets(driver) if (not kp_hits and not ai_hits) else []
 
        merged = []
        seen = set()
        for d in (kp_hits + ai_hits + snip_hits):
            provider_name = clean_provider_name(d.get("providerName", ""))
            addr = _clean(d.get("address", ""))
            phone = normalize_phone(d.get("phone", ""))
 
            if not addr and not phone and not provider_name:
                continue
 
            key = (provider_name, addr, phone)
            if key in seen:
                continue
            seen.add(key)
 
            parsed = parse_us_address(addr)
            conf = compute_confidence(addr, phone, search_item)
 
            merged.append({
                "providerName": provider_name,
                "address": addr,
                "phone": phone,
                "parsed": parsed,
                "confidence": conf,
            })
 
        merged.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return merged
 
 
# =========================
# UI
# =========================
class App:
    def __init__(
        self,
        root: tk.Tk,
        initial_search_item: str,
        auto_search: bool,
        on_done: Callable[[dict], None],
        close_on_copy: bool = True,
    ):
        self.root = root
        self.root.title("Google Provider Address Finder")
        self.root.geometry("1100x650")
        self.is_closing = False
 
        self.searcher = GoogleSearcher()
        self.cache = load_cache()
        self.stop_event = threading.Event()
 
        self.current_results: list[dict] = []
        self.selected_idx = tk.IntVar(value=-1)
 
        self.on_done = on_done
        self.close_on_copy = close_on_copy
        self._done_sent = False
 
        frm = tk.Frame(root, padx=12, pady=12)
        frm.pack(fill="both", expand=True)
 
        tk.Label(frm, text="Search item:").grid(row=0, column=0, sticky="w")
 
        self.entry = tk.Entry(frm, width=140)
        self.entry.grid(row=1, column=0, columnspan=6, sticky="we", pady=(6, 8))
        self.entry.insert(0, initial_search_item or "")
 
        self.status = tk.Label(frm, text="Status: Idle", anchor="w")
        self.status.grid(row=2, column=0, columnspan=4, sticky="we", pady=(0, 6))
 
        self.btn_search = tk.Button(frm, text="Search", width=12, command=self.on_search)
        self.btn_search.grid(row=2, column=4, sticky="e", padx=(6, 0))
 
        self.btn_stop = tk.Button(frm, text="Stop", width=12, command=self.on_stop)
        self.btn_stop.grid(row=2, column=5, sticky="e", padx=(6, 0))
 
        self.results_box = tk.LabelFrame(frm, text=f"Top {TOP_N_ALWAYS} Results (Select One)", padx=10, pady=10)
        self.results_box.grid(row=3, column=0, columnspan=6, sticky="nsew", pady=(10, 10))
 
        self.radios_frame = tk.Frame(self.results_box)
        self.radios_frame.pack(fill="x", expand=False)
 
        self.detail_box = tk.LabelFrame(frm, text="Parsed Output", padx=10, pady=10)
        self.detail_box.grid(row=4, column=0, columnspan=6, sticky="nsew")
 
        self.detail_text = tk.Text(self.detail_box, height=12, wrap="word")
        self.detail_text.pack(fill="both", expand=True)
 
        self.btn_no_result = tk.Button(frm, text="No Result", width=14, command=self.on_close)
        self.btn_no_result.grid(row=5, column=4, sticky="e", pady=(10, 0), padx=(0, 6))
 
        self.btn_copy = tk.Button(frm, text="Copy Address", width=14, command=self.copy_selected_address, state="disabled")
        self.btn_copy.grid(row=5, column=5, sticky="e", pady=(10, 0))
 
        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(3, weight=1)
        frm.grid_rowconfigure(4, weight=1)
 
        self.root.bind("<Return>", lambda _e: self.on_search())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
 
        if auto_search:
            self.root.after(200, self.on_search)
 
    def ui(self, fn):
        try:
            if self.is_closing:
                return
            if not self.root.winfo_exists():
                return
            self.root.after(0, lambda: self._safe_run_ui(fn))
        except Exception:
            pass
 
    def _safe_run_ui(self, fn):
        try:
            if self.is_closing:
                return
            if not self.root.winfo_exists():
                return
            fn()
        except Exception:
            pass
 
    def set_status(self, txt: str):
        self.ui(lambda: self.status.config(text=f"Status: {txt}"))
 
    def _safe_errorbox(self, title: str, exc_text: str):
        self.ui(lambda: messagebox.showerror(title, exc_text))
 
    def on_stop(self):
        self.stop_event.set()
        self.set_status("Stopping...")
 
    def clear_radios(self):
        for w in self.radios_frame.winfo_children():
            w.destroy()
        self.selected_idx.set(-1)
        self.btn_copy.config(state="disabled")
        self.detail_text.delete("1.0", "end")
 
    def render_results_as_radios(self, results: list[dict]):
        self.clear_radios()
        self.current_results = (results or [])[:TOP_N_ALWAYS]
 
        if not self.current_results:
            self.detail_text.insert("end", "No results found.")
            return
 
        def on_select():
            self.show_selected_details()
 
        for i, loc in enumerate(self.current_results):
            parsed = loc.get("parsed") or parse_us_address(loc.get("address", ""))
            phone = normalize_phone(loc.get("phone", ""))
            conf = int(loc.get("confidence", 0))
            name = loc.get("providerName", "")
 
            addr1 = parsed.get("Address Line 1", "")
            city = parsed.get("City", "")
            st = parsed.get("State", "")
            zp = parsed.get("Zip", "")
 
            label = f"{i + 1}. "
            if name:
                label += f"{name} | "
            label += f"{addr1} | {city} {st} {zp}".strip()
            if phone:
                label += f" | {phone}"
            label += f" | {conf}%"
 
            rb = tk.Radiobutton(
                self.radios_frame,
                text=label,
                variable=self.selected_idx,
                value=i,
                anchor="w",
                justify="left",
                command=on_select,
            )
            rb.pack(fill="x", anchor="w", pady=2)
 
        self.selected_idx.set(0)
        self.show_selected_details()
 
    def show_selected_details(self):
        idx = self.selected_idx.get()
        self.detail_text.delete("1.0", "end")
 
        if idx < 0 or idx >= len(self.current_results):
            self.btn_copy.config(state="disabled")
            return
 
        loc = self.current_results[idx]
        parsed = loc.get("parsed") or parse_us_address(loc.get("address", ""))
        phone = normalize_phone(loc.get("phone", ""))
        conf = int(loc.get("confidence", 0))
 
        self.detail_text.insert("end", f"providerName:  {loc.get('providerName', '')}\n")
        self.detail_text.insert("end", f"providerAddr:  {parsed.get('Address Line 1', '')}\n")
        self.detail_text.insert("end", f"providerCity:  {parsed.get('City', '')}\n")
        self.detail_text.insert("end", f"providerState: {parsed.get('State', '')}\n")
        self.detail_text.insert("end", f"providerZip:   {parsed.get('Zip', '')}\n")
        self.detail_text.insert("end", f"providerPhone: {phone}\n")
        self.detail_text.insert("end", f"confidence:    {conf}%\n")
 
        self.btn_copy.config(state="normal")
 
    def set_provider_fields_from_selected(self) -> dict:
        global providerName, providerAddr, providerCity, providerState, providerZip, providerPhone
 
        idx = self.selected_idx.get()
        if idx < 0 or idx >= len(self.current_results):
            raise ValueError("No result selected.")
 
        loc = self.current_results[idx]
        parsed = loc.get("parsed") or parse_us_address(loc.get("address", ""))
        phone = normalize_phone(loc.get("phone", ""))
 
        providerName = loc.get("providerName", "") or ""
        providerAddr = parsed.get("Address Line 1", "")
        providerCity = parsed.get("City", "")
        providerState = parsed.get("State", "")
        providerZip = parsed.get("Zip", "")
        providerPhone = phone
 
        return {
            "providerName": providerName,
            "providerAddr": providerAddr,
            "providerCity": providerCity,
            "providerState": providerState,
            "providerZip": providerZip,
            "providerPhone": providerPhone,
            "selected": idx,
        }
 
    def copy_selected_address(self):
        try:
            picked = self.set_provider_fields_from_selected()
 
            city_line = f"{providerCity}, {providerState} {providerZip}".strip().strip(",")
            clip = "\n".join([
                x for x in [
                    providerName,
                    providerAddr,
                    city_line,
                    f"Telephone: {providerPhone}" if providerPhone else "",
                ] if x.strip()
            ])
 
            self.root.clipboard_clear()
            self.root.clipboard_append(clip)
            self.set_status("Provider variables set + copied to clipboard.")
 
            if self.on_done and not self._done_sent:
                self._done_sent = True
                self.on_done(picked)
 
            if self.close_on_copy:
                self.on_close()
 
        except Exception:
            self.set_status("Error.")
            self._safe_errorbox("Copy Address Error", traceback.format_exc())
 
    def on_search(self):
        search_item = self.entry.get().strip()
        if not search_item:
            self.ui(lambda: messagebox.showwarning("Missing Input", "Please enter a Search item."))
            return
 
        self.stop_event.clear()
        self.ui(lambda: self.btn_search.config(state="disabled"))
        self.set_status("Preparing...")
 
        key = norm_key(search_item)
 
        cached = self.cache.get(key)
        cached_results = None
        if isinstance(cached, dict):
            ts = cached.get("ts", 0)
            if (time.time() - ts) <= CACHE_TTL_SECONDS:
                cached_results = cached.get("results")
 
        def worker():
            try:
                self.ui(self.clear_radios)
 
                if cached_results:
                    self.set_status("Cache hit — using saved results (no Google request).")
                    results = cached_results or []
                    fixed = []
                    for d in results:
                        name = clean_provider_name(d.get("providerName", ""))
                        addr = _clean(d.get("address", ""))
                        phone = normalize_phone(d.get("phone", ""))
                        parsed = d.get("parsed") or parse_us_address(addr)
                        conf = d.get("confidence")
                        if conf is None:
                            conf = compute_confidence(addr, phone, search_item)
                        fixed.append({
                            "providerName": name,
                            "address": addr,
                            "phone": phone,
                            "parsed": parsed,
                            "confidence": int(conf),
                        })
                    fixed.sort(key=lambda x: x.get("confidence", 0), reverse=True)
                    self.ui(lambda fixed=fixed: self.render_results_as_radios(fixed))
                    self.set_status("Done (from cache).")
                    return
 
                self.set_status("Rate limiting (with jitter)...")
                self.searcher.rate_limit()
 
                if self.stop_event.is_set():
                    self.set_status("Stopped.")
                    return
 
                self.set_status("Searching + extracting (Google)...")
                results = self.searcher.run_pipeline(search_item)
 
                if results and results[0].get("_blocked"):
                    wait_s = results[0].get("cooldown_seconds", 0)
                    self.set_status("Blocked / cooling down.")
                    self.ui(lambda wait_s=wait_s: self.detail_text.insert(
                        "end",
                        "Google blocked (CAPTCHA/sorry).\n"
                        f"Cooldown ~{wait_s}s.\n\n"
                        "Tips:\n"
                        " - Keep HEADLESS=False\n"
                        " - Increase BASE_INTERVAL_SECONDS (e.g. 90)\n"
                        " - Avoid repeated searches\n"
                    ))
                    return
 
                try:
                    url = self.searcher.driver.current_url if self.searcher.driver else ""
                    self.cache[key] = {"ts": time.time(), "url": url, "results": results}
                    save_cache(self.cache)
                except Exception:
                    pass
 
                self.ui(lambda results=results: self.render_results_as_radios(results))
                self.set_status("Done.")
 
            except Exception:
                self.set_status("Error.")
                self._safe_errorbox("Search Error", traceback.format_exc())
            finally:
                self.ui(lambda: self.btn_search.config(state="normal"))
        threading.Thread(target=worker,daemon=True).start()
 
    def on_close(self):
        self.is_closing = True
 
        if self.on_done and not self._done_sent:
            self._done_sent = True
            self.on_done({
                "providerName": "",
                "providerAddr": "",
                "providerCity": "",
                "providerState": "",
                "providerZip": "",
                "providerPhone": "",
                "selected": "none",
                "error": "cancelled",
            })
 
        try:
            self.searcher.close()
        except Exception:
            pass
 
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass
 
 
# =========================
# PROGRAMMATIC API FOR FCM
# =========================
def find_provider_address(search_item: str, parent=None) -> dict:
    """
    - Opens UI
    - Auto-searches
    - Blocks until user clicks "Copy Address" or closes (X) or clicks "No Result" (same as X)
    - Returns dict and updates globals providerName/providerAddr/providerCity/providerState/providerZip/providerPhone

    If a parent/root already exists, open as a Toplevel child instead of creating a second Tk root.
    """
    global providerName, providerAddr, providerCity, providerState, providerZip, providerPhone

    search_item = (search_item or "").strip()
    if not search_item:
        return {
            "providerName": "",
            "providerAddr": "",
            "providerCity": "",
            "providerState": "",
            "providerZip": "",
            "providerPhone": "",
            "selected": "none",
            "error": "empty_search_item",
        }

    q: "queue.Queue[dict]" = queue.Queue(maxsize=1)

    def done_cb(result: dict):
        try:
            q.put_nowait(result)
        except Exception:
            pass

    actual_parent = parent
    try:
        if actual_parent is None:
            actual_parent = tk._default_root
    except Exception:
        actual_parent = parent

    if actual_parent is not None:
        try:
            if actual_parent.winfo_exists():
                win = tk.Toplevel(actual_parent)
                win.transient(actual_parent)
                try:
                    win.grab_set()
                except Exception:
                    pass
                App(win, initial_search_item=search_item, auto_search=True, on_done=done_cb, close_on_copy=True)
                actual_parent.wait_window(win)
            else:
                raise RuntimeError("Parent window does not exist.")
        except Exception:
            win = tk.Tk()
            App(win, initial_search_item=search_item, auto_search=True, on_done=done_cb, close_on_copy=True)
            win.mainloop()
    else:
        win = tk.Tk()
        App(win, initial_search_item=search_item, auto_search=True, on_done=done_cb, close_on_copy=True)
        win.mainloop()

    try:
        picked = q.get_nowait()
    except Exception:
        picked = {
            "providerName": "",
            "providerAddr": "",
            "providerCity": "",
            "providerState": "",
            "providerZip": "",
            "providerPhone": "",
            "selected": "none",
            "error": "no_result_returned",
        }

    providerName = picked.get("providerName", "") or ""
    providerAddr = picked.get("providerAddr", "") or ""
    providerCity = picked.get("providerCity", "") or ""
    providerState = picked.get("providerState", "") or ""
    providerZip = picked.get("providerZip", "") or ""
    providerPhone = picked.get("providerPhone", "") or ""

    return picked
 
 
# =========================
# OPTIONAL TEST ENTRY
# =========================
if __name__ == "__main__":
    result = find_provider_address("Roanoke Orthopedics 220 Green St Williamston NC")
    print(result)


