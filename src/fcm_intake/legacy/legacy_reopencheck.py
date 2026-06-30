import pyodbc
from fcm_intake.config import CMS_LOGIN_URL as CONFIG_CMS_LOGIN_URL, EDGE_PATH as CONFIG_EDGE_PATH, IE_DRIVER_PATH as CONFIG_IE_DRIVER_PATH
from dateutil.relativedelta import relativedelta
from pprint import pprint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.ie.service import Service as IeService
from selenium.webdriver.ie.options import Options as IeOptions
from selenium.common.exceptions import WebDriverException, TimeoutException
import time
import tkinter as tk
from tkinter import messagebox
import difflib
import datetime
import os
import subprocess
import re
import sys
 
# -------------------------
# GLOBAL DRIVER MANAGEMENT
# -------------------------
# Single storage for BOTH case number and type
# Example element: {"cms_caseNum": "UO6322", "caseType": "FCM"}
found_cases = []
driver = None  # single reusable Selenium session for this module
 
EDGE_PATH = CONFIG_EDGE_PATH
IE_DRIVER_PATH = CONFIG_IE_DRIVER_PATH
CMS_LOGIN_URL = CONFIG_CMS_LOGIN_URL
 
 
def create_ie_driver():
    """Create a NEW IE-mode driver instance. Only called from get_driver()."""
    Ie_Options = IeOptions()
    Ie_Options.add_additional_option("ie.edgechromium", True)
    Ie_Options.add_additional_option("ie.edgepath", EDGE_PATH)
    Ie_Options.add_additional_option("ignoreProtectedModeSettings", True)
    Ie_Options.add_additional_option("requireWindowFocus", True)
    Ie_Options.add_additional_option("nativeEvents", False)
    Ie_Options.ensure_clean_session = False  # reuse session within this driver
 
    service = IeService(executable_path=IE_DRIVER_PATH)
    drv = webdriver.Ie(service=service, options=Ie_Options)
    drv.maximize_window()
    return drv
 
 
def get_driver():
    """
    Return a live Selenium driver.
    Reuse the global driver if still valid; otherwise create a new one.
    """
    global driver
    if driver is not None:
        try:
            # just touching a property will raise if session is dead
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
    Initialize (or reuse) the IE driver and log into CMS once.
    Safe to call multiple times from other scripts.
    """
    global driver
    driver = get_driver()
    driver.get(CMS_LOGIN_URL)
 
    # OPTIONAL: show a popup only on first login if you still want it
    messagebox.showinfo("Login", "Please Login your genex account")
 
    # Use your legacy_safe_type helper (works with IE mode quirks)
    legacy_safe_type(By.ID, "ctl00_Body_UserName", username)
    time.sleep(1)
    legacy_safe_type(By.ID, "ctl00_Body_Password", password)
    time.sleep(1)
 
    # Accept terms
    iAccept = driver.find_element(By.ID, "ctl00_Body_Accept")
    element_check(iAccept)
    driver.execute_script("AcceptChanged();")
    time.sleep(1)
    # Click login
    loginBtn = driver.find_element(By.ID, "ctl00_Body_Login")
    element_click(loginBtn)
    time.sleep(10)
 
    return driver
 
 
# -------------------------
# DB VALIDATION (no driver)
# -------------------------
 
def validate_cms_case(cms_case_number, sql_conn_string, cms_sql_conn_string):
    """
    Validates a CMS case number against the database (no Selenium here).
    """
    result = {
        'is_valid': False,
        'branch_name': '',
        'message': '',
        'case_status': '',
        'case_enterer': '',
        'assigned_date': None,
        'referral_date': None,
        'case_creation_date': None,
        'received_date': None,
        'closure_date': None,
        'closure_code': '',
        'closure_reason': '',
        'reopen_old_ncm': '',
        'reopen_old_ref_type': '',
        'is_fcm': False,
        'reopen_active': False,
        'reopen_hold': False
    }
 
    min_date = datetime.datetime(4501, 1, 1)  # Equivalent to #1/1/4501#
 
    try:
        # Connect to CMS database
        with pyodbc.connect(cms_sql_conn_string) as conn_cms:
            cursor_cms = conn_cms.cursor()
 
            # Call stored procedure
            cursor_cms.execute(
                "{CALL [CPD].[CPDCaseSearch](?)}",
                (cms_case_number,)
            )
 
            # Defaults
            result['case_status'] = ""
            result['case_enterer'] = ""
            result['assigned_date'] = min_date
            result['referral_date'] = min_date
            result['case_creation_date'] = min_date
            result['received_date'] = min_date
            result['closure_date'] = min_date
            result['closure_code'] = ""
 
            row = cursor_cms.fetchone()
            if row:
                result['is_valid'] = True
 
                # Get branch name from another database
                ar_prefix = cms_case_number[:2]
                sql = (
                    "SELECT RosterName "
                    "FROM [dbo].[RRS_APP_Branch_Contacts_v6] "
                    f"WHERE AR_Prefix = '{ar_prefix}'"
                )
 
                try:
                    with pyodbc.connect(sql_conn_string) as conn:
                        cursor = conn.cursor()
                        cursor.execute(sql)
                        branch_row = cursor.fetchone()
                        if branch_row:
                            result['branch_name'] = branch_row.RosterName
                except Exception as ex:
                    print(f"Error getting branch name: {str(ex)}")
 
                result['message'] = f"Validated In CMS - {result['branch_name']}"
 
                col_names = [column[0] for column in cursor_cms.description]
                row_dict = dict(zip(col_names, row))
 
                result['reopen_old_ncm'] = row_dict.get('AssignedTo', '') or ''
                result['reopen_old_ref_type'] = row_dict.get('ReferralType', '') or ''
 
                if row_dict.get('Casetype'):
                    result['is_fcm'] = (row_dict['Casetype'] == 'FCM')
 
                if row_dict.get('CaseStatus'):
                    result['case_status'] = row_dict['CaseStatus']
 
                if row_dict.get('CaseEnterer'):
                    result['case_enterer'] = row_dict['CaseEnterer']
 
                if row_dict.get('AssignedDate'):
                    result['assigned_date'] = row_dict['AssignedDate']
 
                if row_dict.get('ReceivedDate'):
                    result['received_date'] = row_dict['ReceivedDate']
                    result['referral_date'] = row_dict['ReceivedDate']
 
                if row_dict.get('CaseCreationDate'):
                    result['case_creation_date'] = row_dict['CaseCreationDate']
 
                if row_dict.get('ClosureCode'):
                    result['closure_code'] = row_dict['ClosureCode']
 
                    if result['closure_code'] == "R0613":
                        result['closure_reason'] = "R0613 - Closed, Opened in Error"
                    elif result['closure_code'] == "R0618":
                        result['closure_reason'] = "R0618 - Cancellation of Reopen"
                    elif result['closure_code'] == "R0616":
                        result['closure_reason'] = "R0616 - Carrier Cancellation"
                    elif result['closure_code'] == "R0625":
                        result['closure_reason'] = "R0625 - Closed, Duplicate Referral"
 
                if row_dict.get('ClosureDate'):
                    result['closure_date'] = row_dict['ClosureDate']
                    result['closure_date_formatted'] = result['closure_date'].strftime("%m/%d/%Y")
                    result['reopen_active'] = False
                else:
                    result['reopen_active'] = True
            else:
                result['message'] = "Not valid in CMS"
                result['is_valid'] = False
 
            # Case open?
            if result['case_status'] == "O":
                result['reopen_hold'] = True
                result['reopen_active'] = True
 
            # Not FCM?
            if not result['is_fcm']:
                result['message'] = "The previous case type is not FCM. This case can not be reopened."
                return result
 
            # Check time since closure
            if result['closure_date'] != min_date:
                time_span = datetime.datetime.now() - result['closure_date']
 
                if time_span.days > 365:
                    close_date = result['closure_date'].strftime("%m/%d/%Y")
                    result['message'] = f"CASE IS OVER 365 DAYS SINCE CLOSURE. CLOSED {close_date}"
                    result['is_valid'] = False
 
                elif result['closure_code'] in ["R0613", "R0618", "R0616", "R0625"]:
                    result['message'] = f"{result['closure_reason']}. This referral is ineligible for reopen."
                    result['is_valid'] = False
 
                else:
                    # Format NCM name
                    if result['reopen_old_ncm']:
                        result['reopen_old_ncm'] = result['reopen_old_ncm'].strip()
                        if ", " in result['reopen_old_ncm']:
                            parts = result['reopen_old_ncm'].split(", ")
                            if len(parts) >= 2:
                                last_name = parts[0].strip()
                                first_name = parts[1].strip()
                                result['reopen_old_ncm'] = f"{first_name} {last_name}"
 
                    result['is_valid'] = True
                    result['reopen_hold'] = False
 
    except Exception as ex:
        result['message'] = f"Error validating case: {str(ex)}"
        result['is_valid'] = False
 
    return result
 
 
# -------------------------
# SELENIUM HELPERS
# -------------------------
 
def elementExist(by, value, timeout=10):
    global driver
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        return True
    except Exception:
        return False
 
 
def legacy_safe_type(by, sel, text, timeout=20, click_first=True):
    global driver
    driver = get_driver()
    wait = WebDriverWait(driver, timeout)
    el = wait.until(EC.presence_of_element_located((by, sel)))
 
    driver.execute_script("arguments[0].scrollIntoView(true);", el)
    if click_first:
        try:
            el.click()
        except WebDriverException:
            pass
 
    # Normal typing
    try:
        el.send_keys(Keys.CONTROL, "a")
        el.send_keys(Keys.DELETE)
        el.send_keys(text)
        if el.get_attribute("value") == text:
            return True
    except WebDriverException:
        pass
 
    # JS fallback
    try:
        ok = driver.execute_script(r"""
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
        """, el, text)
        if ok:
            return True
    except WebDriverException:
        pass
 
    return False
 
 
def element_check(el):
    global driver
    driver = get_driver()
    return driver.execute_script(r"""
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
    """, el)
 
 
def element_click(el):
    global driver
    driver = get_driver()
    return driver.execute_script(r"""
        (function(el){
            function idToName(id){ return id.replace(/_/g,'$'); }
            try {
                if (el && el.click) {
                    el.click();
                    return;
                }
            } catch(e){}
            if (typeof window.__doPostBack === 'function') {
                window.__doPostBack(idToName(el.id), '');
                return;
            }
            if (el.form) {
                try { el.form.submit(); return; } catch(e){}
            }
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
    """, el)
 
 
# -------------------------
# WEB CASE VALIDATION (UI)
# -------------------------
 
def ValidateCaseNumber(ClaimNumber):
    """
    Uses the already-logged-in driver to validate a case number via CMS UI.
    Assumes init_cms_session() has been called.
    """
    global driver, found_cases
    driver = get_driver()

    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    driver.get('https://test.genexcms.com/CMS/Default.aspx')

    try:
        WebDriverWait(driver,60).until(
            lambda d: d.execute_script("return document.readyState") == 'complete'
        )
    except Exception:
        pass
    
    time.sleep(2)
    driver.execute_script("h$(0);")
    time.sleep(1)
    driver.execute_script("h$(10);")
    time.sleep(1)
    claimantPfElem = driver.find_element(By.ID, "mmlink1")
    element_click(claimantPfElem)
 
    # Switch to correct frame
    WebDriverWait(driver, 300).until(
        EC.frame_to_be_available_and_switch_to_it((By.XPATH, "/html/body/form/div[5]/iframe"))
    )
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "ctl00_Body_ClaimNumber"))
    )
 
    legacy_safe_type(By.ID, "ctl00_Body_ClaimNumber", ClaimNumber)
 
    searchClaimBtn = driver.find_element(By.ID, "ctl00_Body_SearchButton")
    element_click(searchClaimBtn)
 
    time.sleep(4)
 
    if elementExist(By.XPATH, "/html/body/form/div[3]/table[2]/tbody/tr/td[6]/a"):
        tableClaim = driver.find_element(By.ID, "ctl00_Body_SearchResultsTable_Table")
        claimTrs = tableClaim.find_elements(By.TAG_NAME, "tr")
 
        for row_index in range(1, len(claimTrs)):
            tableClaim = driver.find_element(By.ID, "ctl00_Body_SearchResultsTable_Table")
            claimTrs = tableClaim.find_elements(By.TAG_NAME, "tr")
            claimLink = claimTrs[row_index].find_element(By.TAG_NAME, "a")
            element_click(claimLink)
            time.sleep(3)
 
            table = driver.find_element(By.ID, "ctl00_Body_ClaimantProfileTable_Table")
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", table)
            except WebDriverException:
                pass
 
            rows = table.find_elements(By.TAG_NAME, "tr")
            # for i in range(len(rows)):
            #     claimTxt = rows[i].text.strip()
            #     print(claimTxt)
            #     if ClaimNumber in claimTxt:
            #         try:
            #             caseRow = rows[i + 1]
            #             caseTxt = caseRow.text.strip()
 
            #             # NEW: capture FCM or TCM and the 6-char case number
            #             m = re.search(
            #                 r"Case\s+([FT]CM)\s+([A-Za-z0-9]{6})\b",
            #                 caseTxt,
            #                 re.IGNORECASE
            #             )
            #             if m:
            #                 case_type = m.group(1).upper()   # FCM or TCM
            #                 case_number = m.group(2)
 
            #                 # avoid duplicates
            #                 if not any(c["cms_caseNum"] == case_number for c in found_cases):
            #                     found_cases.append({
            #                         "cms_caseNum": case_number,
            #                         "caseType": case_type
            #                     })
            #                     print(f"Captured case: {case_type} {case_number}")
            #         except Exception as e:
            #             print("Error parsing case row:", e)
            #             pass
            capture = False
            for row in rows:
                text = row.text.strip()
                # print("ROW:", text)
            
                # STEP 1: Start capturing when claim is found
                if ClaimNumber in text:
                    # print(f"START capturing for claim: {text}")
                    capture = True
                    continue
            
                # STEP 2: Stop when next claim is encountered
                if capture and "Claim #" in text:
                    # print("STOP capturing - next claim found")
                    break
            
                # STEP 3: Process case rows while capturing
                if capture and "Case " in text:
                    try:
                        # print("Processing case row:", text)
            
                        m = re.search(
                            r"\bCase\s+(FCM|TCM)\s+([A-Za-z0-9]{5,10})\b",
                            text,
                            re.IGNORECASE
                        )
            
                        if m:
                            case_type = m.group(1).upper()
                            case_number = m.group(2).upper()
            
                            if not any(c["cms_caseNum"] == case_number for c in found_cases):
                                found_cases.append({
                                    "cms_caseNum": case_number,
                                    "caseType": case_type
                                })
                                # print(f"Captured case: {case_type} {case_number}")
            
                    except Exception as e:
                        print("Error parsing case row:", e)
            
            # print("FINAL CASES:", found_cases)


            claimaintListing = driver.find_element(By.XPATH, "/html/body/form/div[3]/div[2]/a")
            element_click(claimaintListing)
            time.sleep(4)
    else:
        print("No claim found")
 
 
# -------------------------
# CONNECTION STRINGS & TEST
# -------------------------
 
CMSconn_str = (
    "DRIVER={SQL Server};"
    "SERVER=cmststdbcluster.Genexservices.com;"
    "DATABASE=CMS;"
    "UID=CPDApplication;"
    "PWD=;"
)
 
RRSconn_str = (
    "DRIVER={SQL Server};"
    "SERVER=tcp:uat-rrs-core-eus-dbs.database.windows.net;"
    "DATABASE=RRS;"
    "UID=RRSApplication;"
    "PWD=;"
)
 
 
def MainReopenCheck(ClaimNumber):
    global found_cases
    found_cases.clear()
 
    drv = init_cms_session("", "")
    ValidateCaseNumber(ClaimNumber)
 
    results = []
    for item in found_cases:
        CMSCase = item["cms_caseNum"]
        caseType = item["caseType"]
 
        case = validate_cms_case(CMSCase, RRSconn_str, CMSconn_str)
        # carry both case number and type into the final result
        caseWithID = {
            "cms_caseNum": CMSCase,
            "caseType": caseType,
            **case
        }
        results.append(caseWithID)
 
    pprint(results)
    drv.quit()
 
    return results
 
 
if __name__ == "__main__":
    results = MainReopenCheck("WC648D18242")





