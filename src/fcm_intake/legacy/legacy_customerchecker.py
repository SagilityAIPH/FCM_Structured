import os
from fcm_intake.config import CMS_LOGIN_URL as CONFIG_CMS_LOGIN_URL, EDGE_PATH as CONFIG_EDGE_PATH, IE_DRIVER_PATH as CONFIG_IE_DRIVER_PATH
import re
import time
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import messagebox, simpledialog

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.ie.options import Options as IeOptions
from selenium.webdriver.ie.service import Service as IeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (TimeoutException,StaleElementReferenceException, NoSuchElementException)
import traceback


# =========================
# PATH RESOLUTION (NO STATIC PATHS)
# =========================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_msedge_path() -> str:
    """
    Try to locate msedge.exe from common Windows install paths.
    You can also override by setting env var EDGE_PATH.
    """
    env = os.environ.get("EDGE_PATH", "").strip() or CONFIG_EDGE_PATH.strip()
    if env and os.path.isfile(env):
        return env

    candidates = [
        # 64-bit install
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # 32-bit install
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        # Per-user install
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
        # If you bundle msedge.exe alongside the script (rare, but allowed)
        os.path.join(SCRIPT_DIR, "msedge.exe"),
        os.path.join(SCRIPT_DIR, "Edge", "msedge.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p

    raise FileNotFoundError(
        "Could not find msedge.exe. Install Microsoft Edge or set environment variable EDGE_PATH "
        "to the full path of msedge.exe."
    )


def find_iedriver_path() -> str:
    """
    Default: use IEDriverServer.exe located in the same folder as this script.
    You can override by setting env var IEDRIVER_PATH.
    """
    env = os.environ.get("IEDRIVER_PATH", "").strip()
    if env and os.path.isfile(env):
        return env

    candidates = [
        CONFIG_IE_DRIVER_PATH,
        os.path.join(SCRIPT_DIR, "drivers", "IEDriverServer.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p

    raise FileNotFoundError(
        "Could not find IEDriverServer.exe. Put IEDriverServer.exe in the same folder as this script "
        "or set environment variable IEDRIVER_PATH to its full path."
    )


# =========================
# APP CONFIG
# =========================
CMS_LOGIN_URL = CONFIG_CMS_LOGIN_URL

# Results table & UI IDs
RESULTS_TABLE_ID = "ctl00_Body_SearchResultsTable_Table"

NAME_FIELD_ID = "ctl00_Body_Name"
ECODE_FIELD_ID = "ctl00_Body_AccountingNumber"
SEARCH_BUTTON_ID = "ctl00_Body_Search"

MENU_SEARCH_CUSTOMER_ID = "mmlink2"
SEARCH_FRAME_XPATH = "/html/body/form/div[5]/iframe"

# Adjust to your tolerance:
# - higher = stricter, fewer auto-picks
# - lower  = more aggressive auto-picks
MIN_MATCH_SCORE = 0.62


# =========================
# GLOBAL DRIVER
# =========================
driver = None


# =========================
# DRIVER / SESSION
# =========================
def create_ie_driver():
    edge_path = find_msedge_path()
    CONFIG_IE_DRIVER_PATH = find_iedriver_path()

    ie_opts = IeOptions()
    ie_opts.add_additional_option("ie.edgechromium", True)
    ie_opts.add_additional_option("ie.edgepath", edge_path)
    ie_opts.add_additional_option("ignoreProtectedModeSettings", True)
    ie_opts.add_additional_option("requireWindowFocus", True)
    ie_opts.add_additional_option("nativeEvents", False)
    ie_opts.ensure_clean_session = False

    service = IeService(executable_path=CONFIG_IE_DRIVER_PATH)
    drv = webdriver.Ie(service=service, options=ie_opts)
    drv.maximize_window()
    return drv


def get_driver():
    global driver
    if driver is not None:
        try:
            _ = driver.current_url
            return driver
        except WebDriverException:
            try:
                driver.quit()
            except Exception:
                pass
            driver = None

    driver = create_ie_driver()
    return driver


def init_cms_session(username: str, password: str):
    """
    Log into CMS once.
    """
    drv = get_driver()
    drv.get(CMS_LOGIN_URL)

    messagebox.showinfo("Login", "Please Login your genex account")

    legacy_safe_type(By.ID, "ctl00_Body_UserName", username)
    time.sleep(0.5)
    legacy_safe_type(By.ID, "ctl00_Body_Password", password)
    time.sleep(0.5)

    iAccept = drv.find_element(By.ID, "ctl00_Body_Accept")
    element_check(iAccept)
    drv.execute_script("AcceptChanged();")
    time.sleep(0.5)

    loginBtn = drv.find_element(By.ID, "ctl00_Body_Login")
    element_click(loginBtn)
    time.sleep(5)
    return drv


# =========================
# SELENIUM HELPERS
# =========================
def elementExist(by, value, timeout=10):
    drv = get_driver()
    try:
        WebDriverWait(drv, timeout).until(EC.presence_of_element_located((by, value)))
        return True
    except Exception:
        return False


def legacy_safe_type(by, sel, text, timeout=20, click_first=True):
    """
    IE-mode friendly typing with JS fallback.
    """
    drv = get_driver()
    wait = WebDriverWait(drv, timeout)
    el = wait.until(EC.presence_of_element_located((by, sel)))

    drv.execute_script("arguments[0].scrollIntoView(true);", el)
    if click_first:
        try:
            el.click()
        except WebDriverException:
            pass

    # Normal typing attempt
    try:
        el.send_keys(Keys.CONTROL, "a")
        el.send_keys(Keys.DELETE)
        el.send_keys(str(text))
        if (el.get_attribute("value") or "") == str(text):
            return True
    except WebDriverException:
        pass

    # JS fallback
    try:
        ok = drv.execute_script(
            r"""
            var el = arguments[0], val = arguments[1];
            try { el.focus && el.focus(); } catch(e){}
            try { el.value = ''; } catch(e){}
            try { el.value = val; } catch(e){}
            if (document.createEventObject && el.fireEvent) {
                try {
                    var ev = document.createEventObject();
                    ev.propertyName = 'value';
                    el.fireEvent('onpropertychange', ev);
                } catch(e){}
                try { el.fireEvent('oninput', document.createEventObject()); } catch(e){}
                try { el.fireEvent('onchange', document.createEventObject()); } catch(e){}
                try { el.fireEvent('onkeyup', document.createEventObject()); } catch(e){}
                try { el.fireEvent('onblur', document.createEventObject()); } catch(e){}
                return el.value === val;
            } else if (document.createEvent) {
                var types = ['input','change','keyup','keydown','blur'];
                for (var i=0;i<types.length;i++){
                    try {
                        var evt = document.createEvent('HTMLEvents');
                        evt.initEvent(types[i], true, false);
                        el.dispatchEvent(evt);
                    } catch(e){}
                }
                return el.value === val;
            } else {
                return el.value === val;
            }
            """,
            el,
            str(text),
        )
        return bool(ok)
    except WebDriverException:
        return False


def element_check(el):
    drv = get_driver()
    return drv.execute_script(
        r"""
        (function(el){
            el.checked = true;
            if (document.createEventObject && el.fireEvent) {
                el.fireEvent('onchange', document.createEventObject());
            } else if (document.createEvent) {
                var e = document.createEvent('Event');
                e.initEvent('change', true, false);
                el.dispatchEvent(e);
            }
        })(arguments[0]);
        """,
        el,
    )


def element_click(el):
    drv = get_driver()
    return drv.execute_script(
        r"""
        (function(el){
            function idToName(id){ return id.replace(/_/g,'$'); }
            try { if (el && el.click) { el.click(); return; } } catch(e){}
            if (typeof window.__doPostBack === 'function') {
                window.__doPostBack(idToName(el.id), '');
                return;
            }
            if (el.form) { try { el.form.submit(); return; } catch(e){} }
            if (document.createEventObject && el.fireEvent) {
                try {
                    el.fireEvent('onmousedown', document.createEventObject());
                    el.fireEvent('onmouseup', document.createEventObject());
                    el.fireEvent('onclick', document.createEventObject());
                    return;
                } catch(e){}
            }
            try { if (typeof el.onclick === 'function') el.onclick(); } catch(e){}
        })(arguments[0]);
        """,
        el,
    )


# =========================
# SEARCH TOKEN LOGIC
# =========================
def SearchCustomerFirstWord(CustomerName: str) -> str:
    """
    - If first word is THE -> return second word
    - If 3+ words and NOT THE -> return first two words
    - Else -> return first word
    """
    if not CustomerName:
        return ""
    
    CustomerName = CustomerName.replace("&", "and")

    cust = " ".join(CustomerName.strip().split())
    words = re.findall(r"[A-Za-z0-9]+", cust)

    if not words:
        return ""

    if words[0].upper() == "THE":
        return words[1] if len(words) > 1 else ""

    if len(words) >= 3:
        return f"{words[0]} {words[1]}"

    return words[0]


# =========================
# NORMALIZATION / ABBREVIATIONS (US commonly used)
# =========================
CORP_MAP = {
    "&": "AND",
    "+": "AND",
    "@": "AT",

    "COMPANY": "CO",
    "CO": "CO",
    "COM": "CO",
    "COS": "CO",
    "COMPANIES": "CO",

    "CORPORATION": "CORP",
    "CORP": "CORP",
    "CORPN": "CORP",
    "CORPORATE": "CORP",

    "INCORPORATED": "INC",
    "INC": "INC",
    "INCO": "INC",

    "LIMITED": "LTD",
    "LTD": "LTD",

    "LIMITEDLIABILITYCOMPANY": "LLC",
    "LIMITEDLIABILITYCO": "LLC",
    "LLC": "LLC",

    "LIMITEDLIABILITYPARTNERSHIP": "LLP",
    "LLP": "LLP",

    "LIMITEDPARTNERSHIP": "LP",
    "LP": "LP",

    "PROFESSIONALCORPORATION": "PC",
    "PROFESSIONALCORP": "PC",
    "PC": "PC",

    "PROFESSIONALASSOCIATION": "PA",
    "PA": "PA",

    "PROFESSIONALLIMITEDLIABILITYCOMPANY": "PLLC",
    "PLLC": "PLLC",

    "ASSOCIATION": "ASSN",
    "ASSN": "ASSN",
    "ASSOC": "ASSN",

    "FOUNDATION": "FDN",
    "FDN": "FDN",

    "INSTITUTE": "INST",
    "INST": "INST",

    "SOCIETY": "SOC",
    "SOC": "SOC",

    "NATIONALASSOCIATION": "NA",
    "NA": "NA",

    "FEDERALCREDITUNION": "FCU",
    "FCU": "FCU",

    "FEDERALSAVINGSBANK": "FSB",
    "FSB": "FSB",

    "HOSPITAL": "HOSP",
    "HOSP": "HOSP",
    "MEDICALCENTER": "MEDCTR",
    "MEDCTR": "MEDCTR",
    "CENTER": "CTR",
    "CTR": "CTR",
    "CLINIC": "CLIN",
    "CLIN": "CLIN",

    "GROUP": "GRP",
    "GRP": "GRP",

    "HOLDINGS": "HLDGS",
    "HLDGS": "HLDGS",
    "HOLDING": "HLDG",
    "HLDG": "HLDG",

    "INTERNATIONAL": "INTL",
    "INTL": "INTL",

    "NATIONAL": "NATL",
    "NATL": "NATL",

    "MANAGEMENT": "MGMT",
    "MGMT": "MGMT",

    "TECHNOLOGIES": "TECH",
    "TECH": "TECH",

    "SYSTEMS": "SYS",
    "SYS": "SYS",

    "SERVICES": "SVC",
    "SVC": "SVC",
    "SERVICE": "SVC",

    "INDUSTRIES": "INDS",
    "INDS": "INDS",

    "ENTERPRISES": "ENT",
    "ENT": "ENT",

    "BENEFITS": "BEN",
    "BEN": "BEN",
    "BENEFIT": "BEN",

    "EMPLOYEES": "EMP",
    "EMP": "EMP",
    "EMPLOYEE": "EMP",
}

STOPWORDS = {"THE", "OF", "FOR", "IN", "AT", "ON", "TO", "A", "AN"}


def normalize_business_name(text: str) -> str:
    if not text:
        return ""
    t = str(text).upper()
    t = t.replace("&", " AND ")
    t = re.sub(r"[^A-Z0-9 ]+", " ", t)  # removes commas and other punctuation
    t = " ".join(t.split())

    tokens = []
    for w in t.split():
        if w in STOPWORDS:
            continue
        w = CORP_MAP.get(w, w)
        tokens.append(w)

    return " ".join(tokens)


def token_set(text: str) -> set:
    return set(normalize_business_name(text).split())


def jaccard(a_tokens: set, b_tokens: set) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def seq_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# =========================
# ECODE
# =========================
ECODE_TO_CUSTOMERS = {
    "E05408": ["COMCAST", "COMCAST CORPORATION"],
    "E00654": ["UPS", "UNITED PARCEL SERVICE"],
    "E11483": ["GOODYEAR TIRE", "THE GOODYEAR TIRE"],
    "E88424": ["QUANTA"],
    "EG0105": ["GENETECH"],
    "E91561": ["CONTINENTAL TIRE"],
    "EA0310": ["NBC", "NATIONAL BROADCASTING"],
}


def get_ecode_for_customer(customer_name: str) -> str:

    name_norm = normalize_business_name(customer_name)
    if not name_norm:
        return ""

    best_ecode = ""
    best_kw = ""

    for ecode, keywords in ECODE_TO_CUSTOMERS.items():
        for kw in keywords:
            kw_norm = normalize_business_name(kw)
            if kw_norm and kw_norm in name_norm and len(kw_norm) > len(best_kw):
                best_kw = kw_norm
                best_ecode = ecode

    return best_ecode


# =========================
# RESULT TABLE: PICK BEST CUSTOMER NAME
# =========================
def pick_first_customer_from_results(drv):
    """
    ECode search rule:
    Use the first valid result row (Type contains 'E') as the best customer name.
    """
    table = WebDriverWait(drv, 30).until(
        EC.presence_of_element_located((By.ID, RESULTS_TABLE_ID))
    )
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    if not rows:
        return None

    for tr in rows:
        tds = tr.find_elements(By.TAG_NAME, "td")
        if len(tds) < 2:
            continue

        type_text = (tds[0].text or "").upper().strip()
        row_name_raw = (tds[1].text or "").strip()

        # same filter you already use: only consider E rows
        if "E" in type_text and row_name_raw:
            return row_name_raw

    return None


def pick_best_customer_from_results(drv, target_customer_name: str, *, min_score: float = MIN_MATCH_SCORE):

    target_norm = normalize_business_name(target_customer_name)
    target_tokens = token_set(target_customer_name)

    table = WebDriverWait(drv, 30).until(
        EC.presence_of_element_located((By.ID, RESULTS_TABLE_ID))
    )
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")

    if not rows:
        return (None, 0.0)

    candidates = []

    for idx, tr in enumerate(rows, start=1):
        tds = tr.find_elements(By.TAG_NAME, "td")
        if len(tds) < 2:
            continue

        type_text = (tds[0].text or "").upper().strip()
        if "E" not in type_text:
            continue

        row_name_raw = (tds[1].text or "").strip()
        if not row_name_raw:
            continue

        row_norm = normalize_business_name(row_name_raw)
        row_tokens = token_set(row_name_raw)

        jac = jaccard(target_tokens, row_tokens)
        coverage = (len(target_tokens & row_tokens) / max(len(target_tokens), 1))
        fuzz = seq_ratio(target_norm, row_norm)

        # Weighted score (token overlap dominates)
        score = (0.55 * jac) + (0.35 * coverage) + (0.10 * fuzz)

        # Tiny tie-breakers (prefer more specific names)
        score += min(len(row_norm), 80) / 8000.0
        score -= idx / 100000.0

        candidates.append((score, row_name_raw))

    if not candidates:
        return (None, 0.0)

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_name = candidates[0]

    if best_score < min_score:
        return (None, best_score)

    return (best_name, best_score)

def _get_result_rows(drv, timeout=20):
    def _rows_ready(d):
        try:
            table = d.find_element(By.ID, RESULTS_TABLE_ID)
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            return rows if len(rows) > 0 else False
        except (StaleElementReferenceException, NoSuchElementException):
            return False
 
    return WebDriverWait(drv, timeout).until(_rows_ready)

# =========================
# PROMPTER (YOUR EXISTING FLOW)
# =========================
def customer_prompter_and_cem(CustomerName: str, ClaimID, ClaimantName, app=None):
    """
    Uses the main FCM Intake Bot UI when available.
    This avoids creating another tk.Tk() from legacy_customerchecker.py.
    """
 
    def ask_yes_no(title, message):
        if app is not None and hasattr(app, "ask_yes_no"):
            return app.ask_yes_no(title, message)
 
        # fallback only when running this file directly
        import tkinter as tk
        from tkinter import messagebox
 
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
 
        try:
            return messagebox.askyesno(title, message, parent=root)
        finally:
            root.destroy()
 
    def ask_text(title, message):
        if app is not None and hasattr(app, "ask_text"):
            return app.ask_text(title, message)
 
        # fallback only when running this file directly
        import tkinter as tk
        from tkinter import simpledialog
 
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
 
        try:
            value = simpledialog.askstring(title, message, parent=root)
            return (value or "").strip()
        finally:
            root.destroy()
 
    has_valid = ask_yes_no(
        "Customer Validation",
        "Is there a valid customer from the result?"
    )
 
    if has_valid:
        name = ask_text(
            "Valid Customer",
            "Please enter valid customer name:"
        )
        return (name or "").strip()
 
    while True:
        manual = ask_yes_no(
            "Manual Search",
            "Please do a manual search.\n\n"
            "Select Yes, if there is a valid customer.\n"
            "Select No, to proceed with CEM Process."
        )
 
        if manual:
            has_valid_2 = ask_yes_no(
                "Customer Validation",
                "Is there a valid customer from the result?"
            )
 
            if has_valid_2:
                name = ask_text(
                    "Valid Customer",
                    "Please enter valid customer name:"
                )
                return (name or "").strip()
 
        need_cem = ask_yes_no(
            "CEM Process",
            "Do you need to complete CEM?"
        )
 
        if need_cem:
            try:
                from legacy import legacy_cem
            except Exception:
                import legacy_cem
 
            legacy_cem.main(CustomerName, ClaimID, ClaimantName)
            return None
 
        # user selected no CEM, continue manual loop
        continue


# def customer_prompter_and_cem(CustomerName: str,ClaimID,ClaimantName):
#     """
#     Uses your interactive prompts when:
#       - no results
#       - bot cannot determine best customer
#       - user rejects suggested customer
#     """
#     root = tk.Tk()
#     root.withdraw()

#     has_valid = messagebox.askyesno("Customer Validation", "Is there a valid customer from the result?")
#     if has_valid:
#         name = simpledialog.askstring("Valid Customer", "Please enter valid customer name")
#         return (name or "").strip()

#     while True:
#         manual = messagebox.askyesno(
#             "Manual Search",
#             "Please do a manual search.\n"
#             "Select Yes, if there is a valid customer\n"
#             "Select No, to proceed with CEM Process."
#         )

#         if manual:
#             has_valid_2 = messagebox.askyesno("Customer Validation", "Is there a valid customer from the result?")
#             if has_valid_2:
#                 name = simpledialog.askstring("Valid Customer", "Please enter valid customer name")
#                 return (name or "").strip()

#             need_cem = messagebox.askyesno("CEM Process", "Do you need to complete CEM?")
#             if need_cem:
#                 import legacy_cem 
#                 legacy_cem.main(CustomerName,ClaimID,ClaimantName)
#                 return None
#             else:
#                 continue
#         else:
#             need_cem = messagebox.askyesno("CEM Process", "Do you need to complete CEM?")
#             if need_cem:
#                 import legacy_cem
#                 legacy_cem.main(CustomerName,ClaimID,ClaimantName)
#                 return None
#             else:
#                 continue


# =========================
# MAIN: VALIDATE CUSTOMER
# =========================
def ValidateCustomer(CustomerName: str,ClaimID,ClaimantName,app=None):
    drv = get_driver()
    
    # Your existing menu navigation JS (kept)
    drv.execute_script("h$(0);")
    time.sleep(1)
    drv.execute_script("h$(9);")
    time.sleep(1)
    drv.execute_script("h$(16);")
    time.sleep(1)

    
    

    search_customer_link = drv.find_element(By.ID, MENU_SEARCH_CUSTOMER_ID)
    element_click(search_customer_link)

    WebDriverWait(drv, 20).until(
        EC.frame_to_be_available_and_switch_to_it((By.XPATH, SEARCH_FRAME_XPATH))
    )

    # Wait for either search field
    WebDriverWait(drv, 60).until(
        lambda d: elementExist(By.ID, NAME_FIELD_ID, timeout=1)
                  or elementExist(By.ID, ECODE_FIELD_ID, timeout=1)
    )
    time.sleep(2)
    # Decide search strategy
    ecode = get_ecode_for_customer(CustomerName)
    used_ecode = bool(ecode)
    
    if ecode:
        legacy_safe_type(By.ID, ECODE_FIELD_ID, ecode)
    else:
        legacy_safe_type(By.ID, NAME_FIELD_ID, SearchCustomerFirstWord(CustomerName))

    # # Click Search
    # search_btn = drv.find_element(By.ID, SEARCH_BUTTON_ID)
    # drv.execute_script("arguments[0].scrollIntoView(true);", search_btn)
    # element_click(search_btn)
    # time.sleep(5)
    # # Wait for results table (table exists even if empty sometimes)
    # WebDriverWait(drv, 60).until(
    #     EC.presence_of_element_located((By.ID, RESULTS_TABLE_ID))
    # )
    
    # table = drv.find_element(By.ID, RESULTS_TABLE_ID)
    # try:
    #     WebDriverWait(drv, 15).until(
    #     lambda d: len(table.find_elements(By.CSS_SELECTOR, "tbody tr")) > 0
    #     )
    # except Exception:
    #     return customer_prompter_and_cem(CustomerName,ClaimID,ClaimantName)
    # rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")

    # Click Search
    search_btn = drv.find_element(By.ID, SEARCH_BUTTON_ID)
    drv.execute_script("arguments[0].scrollIntoView(true);", search_btn)
    element_click(search_btn)
    time.sleep(2)
    
    # Wait for result rows safely
    try:
        rows = _get_result_rows(drv, timeout=25)
    
    except TimeoutException:
        print("[ValidateCustomer] No rows returned after search. Opening customer prompt.")
        
        try:
            name = customer_prompter_and_cem(CustomerName, ClaimID, ClaimantName,app=app)
            print(repr(name))
            if name and str(name).strip():
                return str(name).strip()
        except Exception as e:
            print(f"[ValidateCustomer] customer_prompt_and_cem failed: {type(e).__name__} : {e}")
            traceback.print_exc()
            return None
    
    except Exception as e:
        print(f"[ValidateCustomer] Unexpected customer search error: {e}")
    
        # Retry once before showing the manual prompt
        try:
            search_btn = drv.find_element(By.ID, SEARCH_BUTTON_ID)
            drv.execute_script("arguments[0].scrollIntoView(true);", search_btn)
            element_click(search_btn)
            time.sleep(3)
    
            rows = _get_result_rows(drv, timeout=25)
    
        except Exception as retry_error:
            print(f"[ValidateCustomer] Retry failed: {retry_error}")
            try:
                return customer_prompter_and_cem(CustomerName, ClaimID, ClaimantName,app=app)
            except Exception as prompt_error:
                print(f"[ValidateCustomer] customer_prompt_and_cem failed after retry: {prompt_error}")
                return None


    # Optional: some apps show a "no records found" row as 1 row
    if len(rows) == 1 and "NO RECORD" in (rows[0].text or "").upper():
        return customer_prompter_and_cem(CustomerName,ClaimID,ClaimantName,app=app)

    # If truly no rows -> prompter
    if not rows:
        return customer_prompter_and_cem(CustomerName,ClaimID,ClaimantName,app=app)

    if used_ecode:
        best_name = pick_first_customer_from_results(drv)
        if not best_name:
            return customer_prompter_and_cem(CustomerName,ClaimID,ClaimantName,app=app)

        print(f"[ECODE AUTO-FIRST] {best_name} (ecode={ecode})")
        return best_name
    # Pick best match
    best_name, best_score = pick_best_customer_from_results(drv, CustomerName, min_score=MIN_MATCH_SCORE)

    # If rows exist but bot cannot determine -> prompter
    if not best_name:
        return customer_prompter_and_cem(CustomerName,ClaimID,ClaimantName,app=app)

    # Confirm with user
    # use_it = messagebox.askyesno(
    #     "Customer Found",
    #     f"Found customer:\n\n{best_name}\n\nUse this customer?"
    # )

    # if use_it:
    #     print(f"[AUTO-SELECTED CUSTOMER] {best_name} (score={best_score:.3f})")
    #     return best_name

    if best_name:
        print(f"{best_name}")
        return best_name

    # User rejected -> prompter
    return customer_prompter_and_cem(CustomerName,ClaimID,ClaimantName,app=app)


def MainCustomerCheck(CustomerName: str,ClaimID,ClaimantName,app=None):
    drv = init_cms_session("", "")
    try:
        return ValidateCustomer(CustomerName,ClaimID,ClaimantName,app=app)
    finally:
        try:
            drv.quit()
        except Exception:
            pass


if __name__ == "__main__":
    print(MainCustomerCheck("CARROLS CORPORATION","123456","Test Name"))



