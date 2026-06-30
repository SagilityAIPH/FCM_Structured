
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pprint import pprint 
import time
import glob
import os
import sys
import re
from datetime import datetime
from edge_auto import build_edge_service, find_msedge_path
from fcm_intake.config import ATTACHMENT_FOLDER as CONFIG_ATTACHMENT_FOLDER, EDGE_DRIVER_PATH as CONFIG_EDGE_DRIVER_PATH
 
# ---------- Config ----------
EDGE_DRIVER_PATH = CONFIG_EDGE_DRIVER_PATH
UNITY_URL = 'https://uat-cm-portal-eus-wa.azurewebsites.net/Ng/intervention/dashboard'
ATTACHMENT_FOLDER = CONFIG_ATTACHMENT_FOLDER
 
 
# ---------- Small helpers ----------
def notify(title: str, text: str):
    """Show a messagebox if Tk is available; otherwise print."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost',True)
        messagebox.showinfo(title, text,parent=root)
        root.destroy()
    except Exception:
        print(f"[{title}] {text}")
 
 
def element_exist(driver, by, value, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        return True
    except Exception:
        return False
 
 
def format_str(s: str) -> str:
    return s.replace("\n", " ").replace("\r", "").strip().lower()
 
STATE_MAP = {
    "AL": "Alabama",      "AK": "Alaska",        "AZ": "Arizona",
    "AR": "Arkansas",     "CA": "California",    "CO": "Colorado",
    "CT": "Connecticut",  "DE": "Delaware",      "DC": "District of Columbia",
    "FL": "Florida",      "GA": "Georgia",       "HI": "Hawaii",
    "ID": "Idaho",        "IL": "Illinois",      "IN": "Indiana",
    "IA": "Iowa",         "KS": "Kansas",        "KY": "Kentucky",
    "LA": "Louisiana",    "ME": "Maine",         "MD": "Maryland",
    "MA": "Massachusetts","MI": "Michigan",      "MN": "Minnesota",
    "MS": "Mississippi",  "MO": "Missouri",      "MT": "Montana",
    "NE": "Nebraska",     "NV": "Nevada",        "NH": "New Hampshire",
    "NJ": "New Jersey",   "NM": "New Mexico",    "NY": "New York",
    "NC": "North Carolina","ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma",     "OR": "Oregon",        "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina","SD": "South Dakota",
    "TN": "Tennessee",    "TX": "Texas",         "UT": "Utah",
    "VT": "Vermont",      "VA": "Virginia",      "WA": "Washington",
    "WV": "West Virginia","WI": "Wisconsin",    "WY": "Wyoming",
}
 
def normalize_state_for_dropdown(state: str) -> str:
    if not state:
        return ""
    s = state.strip()
    if len(s) == 2 and s.upper() in STATE_MAP:
        return STATE_MAP[s.upper()]
    return s


# ---------- WebDriver lifecycle ----------
def create_driver():
    opts = EdgeOptions()

    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--allow-insecure-localhost")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    opts.add_argument("--disable-features=OnDeviceModel,OptimizationHints,OptimizationGuideModelDownloading")
    opts.binary_location = find_msedge_path()

    service = build_edge_service(EDGE_DRIVER_PATH)

    driver = webdriver.Edge(service=service, options=opts)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    return driver


 
 
# ---------- Page flows ----------
def login(driver):
    driver.maximize_window()
    driver.get(UNITY_URL)
    WebDriverWait(driver, 15).until(EC.title_contains("Unity"))
 
    unity_handle = driver.current_window_handle
 
    # Find the account chooser window (sometimes same handle)
    WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) >= 1)
    target_handle = None
    for h in driver.window_handles:
        driver.switch_to.window(h)
        try:
            WebDriverWait(driver, 5).until(EC.title_contains("Choose your account"))
            target_handle = h
            break
        except Exception:
            continue
 
    if not target_handle:
        # Sometimes the AAD picker is embedded; try clicking by id directly
        try:
            driver.switch_to.window(unity_handle)
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "AzureADCommonExchange")))
            btn = driver.find_element(By.ID, "AzureADCommonExchange")
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            raise RuntimeError('No window with title containing "Choose your account" found.')
 
    else:
        # In chooser window
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        btn = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "AzureADCommonExchange")))
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", btn)
 
    # Return to Unity and ensure dashboard is loaded
    driver.switch_to.window(unity_handle)
    driver.get(UNITY_URL)
    WebDriverWait(driver, 15).until(EC.title_contains("Unity"))

def LMContinentalTire(allData:dict):
    if "auto" in allData['claimType'].lower() and "continental tire" in allData['customer'].lower() and "mi" in allData['claimStateAbbr'].lower() :
        allData['ServiceType'] ="Medical Task"
        allData['refType'] ="Task"
        allData['CaseObj'] = "MI MCCA Attendant Care"
 
def validate_and_complete_task(driver, customer_name: str, claimant_name: str,dataRef: dict):
    try:
        time.sleep(10)
        notify("Notice", "Checking Intervention Queue.")

        # pprint(dataRef)
 
        # Filter by claimant name
        search_box = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
            By.XPATH,
            "/html/body/my-app/div/div/div/ng-component/div[2]/div/kendo-grid/div/div/div/table/thead/tr[2]/td[2]/kendo-grid-string-filter-cell/kendo-grid-filter-wrapper-cell/kendo-textbox/input"
        )))
        search_box.clear()
        search_box.send_keys(claimant_name)
 
        time.sleep(5)
        first_row = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
            By.XPATH,
            "/html/body/my-app/div/div/div/ng-component/div[2]/div/kendo-grid/div/kendo-grid-list/div/div[1]/table/tbody/tr/td[2]"
        )))
        first_row.click()
 
        time.sleep(5)
        assign_btn = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((
            By.XPATH,
            "/html/body/my-app/div/div/div/ng-component/div[1]/div/div[3]/span/button[1]"
        )))
        assign_btn.click()
 
        time.sleep(3)
        if "auto" in dataRef['claimType'].lower() and "continental tire" in dataRef['customer'].lower() and "mi" in dataRef['claimStateAbbr'].lower() :
            dataRef['ServiceType'] ="Medical Task"
            dataRef['refType'] ="Task"
            dataRef['CaseObj'] = "MI MCCA Attendant Care"

        #Check Adjuster
        #Lawrence, Emeli I
        RawAdjusterName = dataRef['adjuster'].strip()

        searchChecker = False
        try:
            adj_addr = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[3]/div[3]/div/address-form/div/div/div[4]/div/button")))
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", adj_addr)
            adj_addr.click()
            time.sleep(1)
            searchChecker = True
            
            time.sleep(1)
            try:
                use_addr = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[3]/div[3]/div/address-form/suggested-address-modal/modal-template/div/div/div/div[4]/div/div/div/button")))
                use_addr.click()
                time.sleep(1)
            except Exception:
                pass
            ErrorValidateAddr = WebDriverWait(driver,5).until(EC.presence_of_element_located((By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[4]/div/address-form/div/div/div[4]/div/span/span/span[2]")))
            if ErrorValidateAddr:
                notify("Notice",f"Claimant Address is {dataRef['adjAddrFull']}. Manual Process is Needed")
        except Exception:

            pass

        if "," in RawAdjusterName:
            AdjusterLName,restName = [name.strip() for name in RawAdjusterName.split(",", 1)]
            AdjusterFName = restName.split()[0]
        else:
            adjusterNameSplit = RawAdjusterName.split()
            AdjusterFName = adjusterNameSplit[0] if adjusterNameSplit else ""
            AdjusterLName = adjusterNameSplit[-1] if len(adjusterNameSplit)>1 else ""

        if not searchChecker:
            try:
                adjusterName = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[3]/div/div/div[1]")
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", adjusterName)

            except:
                adjusterSearch = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template")
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", adjusterSearch)
                adjusterSearch.click()
                time.sleep(3)

                SearchFName = driver.find_element(By.ID,"intake-search-adjuster-modal-first-name-general-input")
                SearchFName.send_keys(AdjusterFName)
                time.sleep(1)
                SearchLName = driver.find_element(By.ID,"intake-search-adjuster-modal-last-name-general-input")
                SearchLName.send_keys(AdjusterLName)
                time.sleep(1)
                SearchAdjuster = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[2]/div/save-cancel-buttons/span/button[1]")
                SearchAdjuster.click()
                time.sleep(3)
                #Results
                WebDriverWait(driver,120).until(EC.presence_of_all_elements_located((By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div")))
                resultsElem = driver.find_elements(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div")
                if len(resultsElem) > 1:
                    for r in range(1, len(resultsElem)):
                        #Validate result info
                        adName = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div/div[1]")
                        adEmailPhone = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div/div[2]")
                        if AdjusterLName in adName.text:
                            SelectRow = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div")
                            SelectRow.click()
                            time.sleep(2)
                            SelectResult = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[4]/div/button")
                            SelectResult.click()
                            break
                else:
                    
                    CloseResult = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/referral-source/form-section-template/section/div/div/form/div[1]/intake-adjuster-info/form/div/div[2]/div[1]/adjuster-search/form/label/search-form-template/modal-template/div/div/div/div[1]/div[1]/span")
                    CloseResult.click()
                    notify("Notice", "No Results Found for Adjuster, For Manual Input.")

        # Customer name handling
        cust_input_xpath_readonly = (
            "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
            "intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div[1]/general-input/form-control/div/input"
        )
        cust_input_elem = driver.find_element(By.XPATH, cust_input_xpath_readonly)
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", cust_input_elem)
        current_cust_val = cust_input_elem.get_attribute("value")
 
        if current_cust_val == "Not Given / Not Applicable":
            clear_btn = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
                By.XPATH,
                "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                "intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div[2]/button"
            )))
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", clear_btn)
            clear_btn.click()
            time.sleep(3)
 
            typeahead_xpath = (
                "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                "intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div/typeahead/form-control/div/div[1]/input"
            )
            ta = driver.find_element(By.XPATH, typeahead_xpath)
            #ListResult employer
            #/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div/typeahead/form-control/div/div[1]/typeahead-container/ul/li
            clean_customer = re.sub(r"[^A-Za-z0-9 &.]+", "", customer_name)
            if "goodyear tire & rubber co" in clean_customer.lower():
                clean_customer = "goodyear tire & rubber co"
            
            ta.send_keys(clean_customer[:4])
            time.sleep(3)

            countSearch = driver.find_elements(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                    "intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div/typeahead/form-control/div/div[1]/"
                    "typeahead-container/ul/li")
            
            if len(countSearch) > 1:
                notify("Notify","Manual Selection Required for multiple results.")
            elif len(countSearch) == 1:
                try:

                    first_pick = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                        By.XPATH,
                        "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                        "intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div/typeahead/form-control/div/div[1]/"
                        "typeahead-container/ul/li[1]"
                    )))
                    first_pick.click()
                    time.sleep(3)
                except Exception:
                    notify("Notice", "Unable to search Employer, Please try manual employer search.")#proceeding to CEM process
            else:
                ta.clear()
                ta.send_keys("Not Given / Not Applicable")
                try:

                    first_pick = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                        By.XPATH,
                        "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                        "intake-customer-info/form-section-template/section/div/div/form/div[4]/div/div/typeahead/form-control/div/div[1]/"
                        "typeahead-container/ul/li[1]"
                    )))
                    first_pick.click()
                    time.sleep(3)
                except:
                    pass
                notify("Notify","Manual Selection Require.")
                # try:
                #     ta = driver.find_element(By.XPATH, typeahead_xpath)
                #     ta.send_keys(Keys.CONTROL, "a")
                #     ta.send_keys(Keys.DELETE)
                #     ta.send_keys("Not Given")
                #     time.sleep(1)
                #     ta.send_keys(Keys.ENTER)
                #     time.sleep(2)
                # except Exception:
                #     pass
                # # Optional: call CEM if available
                # try:
                #     import CEM as CEMBot
                #     CEMBot.main()
                # except Exception:
                #     pass
        #------------Service Types---------------
        ServiceType = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-service-type/form-section-template/section/div/div/form/div[3]/div[1]/select-input/form-control/div/div/select")
        RefType = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-service-type/form-section-template/section/div/div/form/div[3]/div[2]/select-input/form-control/div/div/select")
        CaseObjective = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-service-type/form-section-template/section/div/div/form/div[3]/div[3]/select-input/form-control/div/div/select")


#'refType':'Medical',
#  'serviceType' : 'Medical Full',
#  'caseObj': 'Coordination of Care/Services'

        select = Select(ServiceType)
        ServiceTypeSelected = select.all_selected_options
        if not ServiceTypeSelected:
        # if not ServiceType:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ServiceType)
            # 1 - Medical Full
            # 2 - Medical Task
            # 3 - Vocational Full
            # 4 - Vocational Task
            # 5 - Employer
            # 6 - Other Services
            # select = Select(ServiceType)
            if "medical full" in dataRef['serviceType'].lower():
                select.select_by_value("1")
            elif "medical task" in dataRef['serviceType'].lower():
                select.select_by_value("2")
            elif "vocational full" in dataRef['serviceType'].lower():
                select.select_by_value("3")
            elif "vocational task" in dataRef['serviceType'].lower():
                select.select_by_value("4")
            elif "employer" in dataRef['serviceType'].lower():
                select.select_by_value("5")
            elif "other services" in dataRef['serviceType'].lower():
                select.select_by_value("6")
            time.sleep(1)
            
        select = Select(RefType)
        RefTypeSelected = select.all_selected_options
        if not RefTypeSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", RefType)
            # select = Select(RefType)
            if "medical full" in dataRef['serviceType']:
                select.select_by_visible_text("Medical")
                time.sleep(1)
            
        select = Select(CaseObjective)
        CaseObjectiveSelected = select.all_selected_options
        if not CaseObjectiveSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", CaseObjective)
            select = Select(CaseObjective)
            if "medical full" in dataRef['serviceType']:
                select.select_by_visible_text("Coordination of Care/Services")
                time.sleep(1)


        # ---- Claim search by number/ Claim Info ----
        # claim_num_xpath = (
        #     "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
        #     "intake-claim-info/form-section-template/section/div/div/form/div[2]/div[1]/general-input/form-control/div/input"
        # )
        # claim_num_elem = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, claim_num_xpath)))
        # driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", claim_num_elem)
        # claim_number = claim_num_elem.get_attribute("value")
        # time.sleep(1)
 
        # search_trigger_xpath = (
        #     "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
        #     "intake-claim-info/form-section-template/section/div/div/form/div[1]/claim-claimant-search/label/search-form-template"
        # )
        # search_input_xpath = (
        #     "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
        #     "intake-claim-info/form-section-template/section/div/div/form/div[1]/claim-claimant-search/label/search-form-template/"
        #     "modal-template/div/div/div/div[3]/div/div/div/div[1]/div[2]/div[2]/general-input/form-control/div/input"
        # )
        # search_btn_xpath = (
        #     "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
        #     "intake-claim-info/form-section-template/section/div/div/form/div[1]/claim-claimant-search/label/search-form-template/"
        #     "modal-template/div/div/div/div[3]/div/div/div/div[2]/div/save-cancel-buttons/span/button[1]"
        # )
        # nores_xpath = (
        #     "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
        #     "intake-claim-info/form-section-template/section/div/div/form/div[1]/claim-claimant-search/label/search-form-template/"
        #     "modal-template/div/div/div/div[3]/div/div/div/div[3]/div"
        # )
        # close_modal_xpath = (
        #     "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
        #     "intake-claim-info/form-section-template/section/div/div/form/div[1]/claim-claimant-search/label/search-form-template/"
        #     "modal-template/div/div/div/div[1]/div[1]/span"
        # )
 
        # search_trigger = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, search_trigger_xpath)))
        # driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", search_trigger)
        # search_trigger.click()
        # time.sleep(1)
 
        # search_input = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, search_input_xpath)))
        # driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", search_input)
        # search_input.clear()
        # search_input.send_keys(claim_number)
        # time.sleep(1)
 
        # search_go = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, search_btn_xpath)))
        # driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", search_go)
        # search_go.click()
        # time.sleep(3)
 
        # claim_results = driver.find_elements(By.XPATH, nores_xpath)
        # if len(claim_results) < 2:
        #     try:
        #         close_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, close_modal_xpath)))
        #         close_btn.click()
        #     except Exception:
        #         pass
        
        ClaimType = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claim-info/form-section-template/section/div/div/form/div[2]/div[2]/select-input/form-control/div/div/select")
        select = Select(ClaimType)
        ClaimTypeSelected = select.all_selected_options
        if not ClaimTypeSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ClaimType)
            select.select_by_visible_text("Lost Time")
            time.sleep(1)
        
        # dataRef['claimStateFull']
        Jurisdiction= driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claim-info/form-section-template/section/div/div/form/div[2]/div[3]/select-input/form-control/div/div/select")
        select = Select(Jurisdiction)
        JurisdictionSelected = select.all_selected_options
        if not JurisdictionSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", Jurisdiction)
            select.select_by_visible_text(dataRef['claimStateFull'])
            
        doi_xpath = (
            "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
            "intake-claim-info/form-section-template/section/div/div/form/div[4]/div[1]/date-input/form-control/div/div/input"
        )
        dod_xpath = (
            "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
            "intake-claim-info/form-section-template/section/div/div/form/div[4]/div[2]/date-input/form-control/div/div/input"
        )
        doi = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, doi_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", doi)
        time.sleep(1)
        dod = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, dod_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", dod)
        doi_val = doi.get_attribute("value")
        try:
            dod.clear()
        except Exception:
            pass
        dod.send_keys(doi_val)
        time.sleep(1)
        LOI = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claim-info/form-section-template/section/div/div/form/div[4]/div[3]/select-input/form-control/div/div/select")
        select = Select(LOI)
        LOISelected = select.all_selected_options
        if not LOISelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", LOI)
            select.select_by_visible_text(dataRef['claimType'])
            time.sleep(1)
        BodyPart= driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claim-info/form-section-template/section/div/div/form/div[5]/div[1]/select-input/form-control/div/div/select")
        # if not BodyPart :
        select = Select(BodyPart)
        BodyPartSelected = select.all_selected_options
        if not BodyPartSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", BodyPart)
            select.select_by_visible_text(dataRef['bodyPart'])
            time.sleep(1)

        InjType= driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claim-info/form-section-template/section/div/div/form/div[5]/div[2]/select-input/form-control/div/div/select")
        # if not InjType :
        select = Select(InjType)
        InjTypeSelected = select.all_selected_options
        if not InjTypeSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", InjType)
            select.select_by_visible_text(dataRef['injuryType'])
            time.sleep(1)
            
        InjCause= driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claim-info/form-section-template/section/div/div/form/div[5]/div[3]/select-input/form-control/div/div/select")
        # if not InjCause :
        select = Select(InjCause)
        InjCauseSelected = select.all_selected_options
        if not InjCauseSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", InjCause)
            try:
                select.select_by_visible_text(dataRef['injuryCause'])
                time.sleep(1)
            except:
                InjCauseSelected = select.all_selected_options
                if not InjCauseSelected:
                    notify("Notice",f"Injury Cause is : {dataRef['injuryCause']}. Agent to select Injury Cause Manually")

        #SSN 999
        # 
        SSNElement = driver.find_element(By.ID,"intake-claimant-social-security-number-ssn-input")
        SSNVal = SSNElement.get_attribute("value")
        if SSNVal[:3].strip() == "999":
            SSNElement.clear()

        #Defense Attorney
        def getYesNoSection(driver,control_Name:str):
            xpath = (f"//button-group-input[@formcontrolname='{control_Name}']"
                     f"/ancestor::div[contains(@class,'col-sm-12')][1]"
                     )
            
            section = WebDriverWait(driver,3).until(EC.presence_of_element_located((By.XPATH,xpath)))
            return section
        
        def ExtractDefenseAtty(section):
            header = section.find_element(
                By.XPATH,".//div[contains(@class,'panel-heading') or contains(@class,'card-header')]"
            )
            DefenseAttyName = header.text.strip()
            return DefenseAttyName

        def DoDefAttySearch(section):
            searchDef = section.find_element(By.XPATH,".//attorney-search//i[contains(@class,'fa-search')]")
            searchDef.click()
            notify("Notice","For user manual process")

        attorney_section = getYesNoSection(driver,"hasDefenseAttorney")
        btn = attorney_section.find_element(By.XPATH,".//button[contains(@class,'selected')]")
        hasDefAtty = btn.text.strip()

        if hasDefAtty.lower()=="yes":
            if not ExtractDefenseAtty:
                DoDefAttySearch()


        #------- Claimant Info --------
        ClaimantFName = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[1]/div[1]/general-input/form-control/div/input")
        ClaimantFNameSelected = ClaimantFName.get_attribute("value")
        if not ClaimantFNameSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ClaimantFName)
            ClaimantFName.send_keys(dataRef['claimantFirst'])

        ClaimantLName = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[1]/div[2]/general-input/form-control/div/input")
        ClaimantLNameSelected = ClaimantLName.get_attribute("value")
        if not ClaimantLNameSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ClaimantLName)
            ClaimantLName.send_keys(dataRef['claimantLast'])

        ClaimantGender = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[1]/div[3]/select-input/form-control/div/div/select")
        select = Select(ClaimantGender)
        ClaimantGenderSelected = select.all_selected_options
        if not ClaimantGenderSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ClaimantGender)
            select.select_by_visible_text(dataRef['gender'])

        ClaimantDOB = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[2]/div[1]/date-input/form-control/div/div/input")
        ClaimantDOBSelected = ClaimantDOB.get_attribute("value")
        if not ClaimantDOBSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ClaimantDOB)
            ClaimantDOB.send_keys(dataRef['dob'])

        ClaimantPhone = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[3]/div[1]/phone-input/form-control/div/input")
        ClaimantPhoneSelected = ClaimantPhone.get_attribute("value")
        if not ClaimantPhoneSelected:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", ClaimantPhone)
            ClaimantPhone.send_keys(dataRef['phoneNumber'])


        # ---- Address validations (best-effort) ---- #Claimant addr
        try:
            v_addr = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
                By.XPATH,
                "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                "intake-claimant/form-section-template/section/div/div/form/div[4]/div/address-form/div/div/div[4]/div/button"
            )))
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", v_addr)
            v_addr.click()

            
            time.sleep(1)
            try:
                use_addr = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
                    By.XPATH,
                    "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                    "intake-claimant/form-section-template/section/div/div/form/div[4]/div/address-form/suggested-address-modal/"
                    "modal-template/div/div/div/div[4]/div/div/div/button"
                )))
                use_addr.click()
            except Exception:
                pass
            ErrorValidateAddr = WebDriverWait(driver,5).until(EC.presence_of_element_located((By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[4]/div/address-form/div/div/div[4]/div/span/span/span[2]")))
            if ErrorValidateAddr:
                notify("Notice",f"Claimant Address is {dataRef['addressLine1']} {dataRef['city']} {dataRef['state']} {dataRef['zip']}. Manual Process is Needed")
        except Exception:
            pass

            
        #--------------- Atty Details ----------------
        #add YesNo
        #Attorney
        def splitName(attyName:str):
            if not attyName.strip():
                return "",""
            
            attyName = attyName.strip()
            if "," in attyName:
                last,first_part = [x.strip() for x in attyName.split(",",1)]
                first_token = first_part.split()
                first = first_token[0] if first_token else ""
                return first,last
            parts = attyName.split()
            if len(parts) == 1:
                return parts[0],""
            else:
                first = parts[0]
                last = parts[-1]
                return first,last
        claimantAttyName = dataRef['claimantAttyName']
        claimantAttyFName,claimantAttyLName = splitName(claimantAttyName)
        claimantAttyAddr1 = dataRef['claimantAttyAddr1']
        claimantAttyAddr2 = dataRef['claimantAttyAddr2']
        claimantAttyCity = dataRef['claimantAttyAddr2']
        claimantAttyState = dataRef['claimantAttyState']
        claimantAttyZip = dataRef['claimantAttyZip']
        claimantAttyPhone = dataRef['claimantAttyPhone']

        def ExtractAtty(section):
            try:
                headers = section.find_elements(By.XPATH,
                                            (".//following::div["
                                            " (contains(@class,'panel-heading') or contains(@class,'card-header'))"
                                            " and ancestor::intake-attorney-info"
                                            "][1]"
                                            )
                                            )   #./following-sibling::intake-attorney-info[1]
                if not headers:
                    return None
                return headers[0].text.strip()
            except TimeoutException:
                return None
        def wait_for_attorney_search_results(driver, timeout: int = 10) -> int:
            wait = WebDriverWait(driver, timeout)
            try:
                # no_results = driver.find_elements(
                no_results = wait.until(EC.visibility_of_element_located((  
                By.XPATH,
                "//div[contains(@class,'search-results')]//div[contains(@class,'col-xs-12') and normalize-space()='No results']"
                )))
                if no_results:
                    return 0
                return 0
            except:pass
            
            
            loading_loc = (
                By.XPATH,
                "//span[contains(@class,'text-muted') and contains(normalize-space(),'Loading results')]"
            )
            try:
                wait.until(EC.visibility_of_element_located(loading_loc))
            except TimeoutException:
                pass  
            try:
                wait.until(EC.invisibility_of_element_located(loading_loc))
            except TimeoutException:
                return 0
            rows = driver.find_elements(By.XPATH, "//div[@result-body]/div")
            if rows:
                return len(rows)
        
            no_results = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'search-results')]//div[contains(@class,'col-xs-12') and normalize-space()='No results']"
            )
            if no_results:
                return 0
            return 0



        def DoAttySearch(section):
            searchDef = section.find_element(By.XPATH,".//attorney-search//i[contains(@class,'fa-search')]")
            searchDef.click()

            dialogForm = WebDriverWait(driver,5).until(
                EC.visibility_of_element_located((By.XPATH,"//[contains(@class,'modal') and .//h3[normalize-space()='Search Attorney']]"))
            )

            if claimantAttyFName and claimantAttyLName:
                firstInput = dialogForm.find_element(By.ID,"intake-attorney-info-search-first-name-general-input")
                lastInput = dialogForm.find_element(By.ID,"intake-attorney-info-search-last-name-general-input")
                firstInput.clear()
                firstInput.send_keys(claimantAttyFName[:3])
                lastInput.clear()
                lastInput.send_keys(claimantAttyLName[:3])
            if claimantAttyPhone:
                phone = dialogForm.find_element(By.ID,"intake-attorney-info-search-phone-number-phone-input")
                phone.clear()
                phone.send_keys(claimantAttyPhone)
            
            Searchbtn = dialogForm.find_element(By.XPATH,".//button[@type='button and normalize-space()='Search']")
            Searchbtn.click()

            resultCount = wait_for_attorney_search_results(driver)
            if resultCount >= 1:
                notify("Notice","For Manual Process. Please validate the result.")
            else:
                def askUserContinue():
                    import tkinter as tk
                    from tkinter import messagebox
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes('-topmost',True)
                    answer = messagebox.askyesno("User Confirmation","No Results found. Do you want to add Attorney?\nSelect Yes to manually add attorney. \nSelect No if the user will manually search for the Attorney.")
                    if answer:
                        return True
                    else:
                        return False
                    
                botStop = askUserContinue()
                if botStop:
                    closeModal = dialogForm.find_element(By.XPATH,".//span[contains(@class,'close-button')]")
                    closeModal.click()
                    time.sleep(3)
                    addnewClmAtty = attorney_section.find_element(By.XPATH,".//button[normalize-space()='Add new Attorney']")
                    addnewClmAtty.click()

                    wait = WebDriverWait(driver,10)
                    firstNameAtty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-first-name-general-input")))
                    lastNameAtty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-last-name-general-input")))
                    addr1Atty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-address-1-general-input")))
                    addr2Atty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-address-2-general-input")))
                    cityAtty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-city-general-input")))
                    stateAtty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-state-select-input")))
                    zipAtty = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-zip-code-zip-code-input")))

                    firstNameAtty.clear()
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", firstNameAtty)
                    firstNameAtty.send_keys(claimantAttyFName)

                    lastNameAtty.clear()
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", lastNameAtty)
                    lastNameAtty.send_keys(claimantAttyLName)

                    addr1Atty.clear()
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", addr1Atty)
                    addr1Atty.send_keys(claimantAttyAddr1)

                    addr2Atty.clear()
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", addr2Atty)
                    addr2Atty.send_keys(claimantAttyAddr2)

                    cityAtty.clear()
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", cityAtty)
                    cityAtty.send_keys(claimantAttyCity)

                    # stateAtty.clear()
                    selAttyState = Select(stateAtty)
                    state_text = normalize_state_for_dropdown(claimantAttyState)
                    if state_text:
                        selAttyState.select_by_visible_text(state_text)

                    zipAtty.clear()
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", zipAtty)
                    zipAtty.send_keys(claimantAttyZip)

            
                # notify("Notice","For user manual process")

        attorney_section = getYesNoSection(driver,"hasAttorney")
        btn = attorney_section.find_element(By.XPATH,".//button[contains(@class,'selected')]")
        btnYes = attorney_section.find_element(By.XPATH,".//button[normalize-space()='Yes']")
        btnNo = attorney_section.find_element(By.XPATH,".//button[normalize-space()='No']")
        btnYesVal = btnYes.text.strip()
        hasAtty = btn.text.strip()

        if claimantAttyName and hasAtty.lower() == "no":
            btnYes.click()
        if not claimantAttyName and hasAtty.lower() == "yes":
            btnNo.click()

        checkAttyFirst = "N/A"
        checkAttyLast= "N/A"    
        try:
            firstNameAttyCheck = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-first-name-general-input")))
            lastNameAttyCheck = wait.until(EC.visibility_of_element_located((By.ID,"intake-attorney-info-last-name-general-input")))
            checkAttyFirst = firstNameAttyCheck.get_attribute("value")
            checkAttyLast = lastNameAttyCheck.get_attribute("value")
        except:
            pass

        if hasAtty.lower()=="yes":
            
            if not ExtractAtty(attorney_section) and (checkAttyFirst  != "N/A" and checkAttyLast != "N/A"):
                    DoAttySearch(attorney_section)
            
            # if checkAttyFirst  == "N/A" and checkAttyLast == "N/A" and ExtractAtty(attorney_section):
            #         DoAttySearch(attorney_section)

            try:
                # clmAttyValidateAddr = attorney_section.find_element(By.XPATH,".//button[normalize-space()='Validate Address']")
                wait = WebDriverWait(driver,3)
                clmAttyValidateAddr = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//intake-attorney-info[@id='claimant-attorney-info']"
                            "//address-form[@id='address']"
                            "//button[contains(@class,'secondary') and normalize-space()='Validate Address']"
                        )
                    )
                )




                if clmAttyValidateAddr:
                    clmAttyValidateAddr.click()
                    time.sleep(1)
                    try:
                        wait = WebDriverWait(driver, 10)

                        xpath_use = (
                            "//div[@role='dialog' and contains(@class,'modal') "
                            "     and contains(@class,'in') and @aria-hidden='false']"
                            "//button[contains(@class,'secondary') and normalize-space()='Use']"
                        )

                        useAddr = wait.until(
                            EC.element_to_be_clickable((
                                By.XPATH,
                                xpath_use
                            ))
                        )
                        useAddr.click()
                    except:
                        exc_type, exc_obj, tb = sys.exc_info()
                        print(f"error occurred: {ex} (line {tb.tb_lineno})")
            # except Exception as ex:
            #     exc_type, exc_obj, tb = sys.exc_info()
            #     print(f"error occurred: {ex} (line {tb.tb_lineno})")
            except:
                # exc_type, exc_obj, tb = sys.exc_info()
                # print(f"error occurred: {ex} (line {tb.tb_lineno})")
                pass

        #old Atty
        # claimAttyName = dataRef['claimantAttyName']
        # if claimAttyName:
        #     try:
        #         AttyName = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[2]/div/div/div[1]")

        #     except:
        #         SearchAtty = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template")
        #         SearchAtty.click()

        #         AttyFName = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[1]/div[1]/div[1]/general-input/form-control/div/input")
        #         AttyLName = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[1]/div[1]/div[2]/general-input/form-control/div/input")
        #         SearchAttyBtn = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[2]/div[2]/save-cancel-buttons/span/button[1]")

        #         ResultsElem = driver.find_elements(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div")
        #         if len(ResultsElem) > 1:
        #             for r in range(1, len(ResultsElem)):
        #                 #Validate result info check also Addr and Phone
        #                 attyRName = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div/div[1]")
        #                 attyRAddr = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div/div[2]")
        #                 attyRPhone = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div/div[3]")
        #                 if AttyLName in attyRName.text:
        #                     SelectRow = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[3]/div/div/div/div[3]/div/div/div[2]/div/div/div[{r}]/search-result-template/div")
        #                     SelectRow.click()
        #                     time.sleep(2)
        #                     SelectResult = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[4]/div/button")
        #                     SelectResult.click()
        #                     break
        #         else:
                    
        #             CloseResult = driver.find_element(By.XPATH,f"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[6]/intake-attorney-info/form/div/div[1]/div[1]/attorney-search/form/label/search-form-template/modal-template/div/div/div/div[1]/div[1]/span")
        #             CloseResult.click()
        #             notify("Notice", "No Results Found for Attorney, For Manual Input.")

         # ---------- Always run the final steps below even if above was best-effort ----------
        providerName = dataRef['providerName']
        providerLast= dataRef['providerLast']
        providerFirst= dataRef['providerFirst']
        providerAddr = dataRef['providerAddr']
        providerCity = dataRef['providerCity']
        providerState = dataRef['providerState']
        providerZip = dataRef['providerZip']


        if (providerName or (providerFirst or providerLast)) or (dataRef['nextApptDate']): # and dataRef['nextApptTime']

            prv_section = getYesNoSection(driver,"hasAppointmentWithProvider")
            btn = prv_section.find_element(By.XPATH,".//button[contains(@class,'selected')]")
            btnYes = prv_section.find_element(By.XPATH,".//button[normalize-space()='Yes']")
            btnNo = prv_section.find_element(By.XPATH,".//button[normalize-space()='No']")
            btnYesVal = btnYes.text.strip()
            hasPrv = btn.text.strip()

            if ((providerName or (providerFirst or providerLast)) or (dataRef['nextApptDate'] )) and hasPrv.lower() == "no": #and dataRef['nextApptTime']
                btnYes.click()
            if not((providerName or (providerFirst or providerLast)) or (dataRef['nextApptDate'] )) and hasPrv.lower() == "yes": #and dataRef['nextApptTime']
                btnNo.click()

            #/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[{index}]/div/button-group-input/form-control/div/div/button[1] # 7
            # prv_section = getYesNoSection(driver,"hasAppointmentWithProvider")
            # btn = prv_section.find_element(By.XPATH,".//button[contains(@class,'selected')]")
            # hasPrv = btn.text.strip()

            # if hasPrv.lower() == "yes":
            #     pass

            # prvYes = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/intake-claimant/form-section-template/section/div/div/form/div[7]/div/button-group-input/form-control/div/div/button[1]")
            # prvYesClass = prvYes.get_attribute("class") or ""
            # if "selected" not in prvYesClass.split():
            #     prvYes.click()
            # Appointment date = today
            if dataRef['nextApptDate'] : #and dataRef['nextApptTime']
                if dataRef['nextApptDate']:
                    appt_id = "intake-provider-appointment-date-date-input"
                    try:
                        appt = driver.find_element(By.ID, appt_id)
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", appt)
                        appt.send_keys(Keys.CONTROL, "a")
                        appt.send_keys(Keys.DELETE)
                        today_str = datetime.today().strftime("%m/%d/%Y")
                        appt.send_keys(today_str)
                        time.sleep(3)
                        # dropdownTime = driver.find_element(By.ID, "intake-provider-time-zone-select-input")
                        # selectTimeZone = Select(dropdownTime)
                        # selectTimeZone.select_by_visible_text("Pacific Standard Time")
                    except Exception:
                        pass
            
            # if not dataRef['nextApptTime']:
            #     flag = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/div[1]/div/div[1]/span")
            #     if flag:
            #         flag.click()
            #         time.sleep(2)
            #         missingInfo = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/flag-for-intervention-modal/modal-template/div/div/div/div[3]/div/form/div/div[1]/radio-group-input/form-control/div/label/div[1]/div/i[1]")
            #         missingInfo.click()
            #         time.sleep(2)
            #         missingDescription = driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/flag-for-intervention-modal/modal-template/div/div/div/div[3]/div/form/div/div[3]/text-area/form-control/div/textarea")
            #         missingDescription.send_keys("Missing Provider Appointment Time")
            #         time.sleep(2)
            #         flagReferral =  driver.find_element(By.XPATH,"/html/body/my-app/div/div/div/ng-component/flag-for-intervention-modal/modal-template/div/div/div/div[4]/div/div/div/button")
            #         flagReferral.click()
            #         time.sleep(2)

            
            # provider address variants (optional blocks, swallow errors)
            #----------------- Provider Info ---------------------
            def ValidateAddrPrv(section):
                try:
                    providerSection = section.find_element(By.XPATH,".//following::intake-provider-info[@id='provider-info'][1]")
                    # finds a line that has "Address" and somewhere near it "Invalid address"
                    # invalid_elems = providerSection.find_element(
                    # By.XPATH,
                    # ".//*[contains(translate(normalize-space(.),"
                    # " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                    # " 'invalid address')]"
                    # )
                    print(providerSection.text.lower())
                    if 'validated' in providerSection.text.lower():
                        return True
                    # if 'invalid address' in providerSection.text.lower():

                    providerValidateAddr = providerSection.find_element(By.XPATH,".//button[normalize-space()='Validate Address']")
                    if providerValidateAddr:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", providerValidateAddr)
                        providerValidateAddr.click()
                        time.sleep(2)
                        try:
                            # modalAddress = WebDriverWait(driver,3).until(
                            #     EC.visibility_of_element_located(
                            #         (By.XPATH,
                            #         "//div[contains(@class,'modal-dialog')"
                            #         " and .//h1[contains(normalize-space(),"
                            #         "'The address that was found did not match')]]"
                            #         )
                            #     )
                            # )
                            # modalAddress.click()
                            # use_xpath = (
                            #     "//div[contains(@class,'modal-dialog') and "
                            #     "contains(@style,'display: block')]"   # visible dialog only
                            #     "//button[normalize-space()='Use']"
                            # )

                            use_xpath = (
                            # visible modal (has 'modal', 'fade', 'in')
                            "//div[contains(@class,'modal') and contains(@class,'fade') and contains(@class,'in')]"
                            # descendant button with text 'Use'
                            "//button[normalize-space()='Use']"
                            )



                            useAddr =  WebDriverWait(driver,3).until(EC.element_to_be_clickable((By.XPATH,use_xpath)))#".//button[normalize-space()='Use']"
                            useAddr.click()
                            return True
                        except:
                            return False
                except:
                    return False
        divCount = 0
        if providerName or (providerFirst or providerLast):
            providerSection = prv_section.find_element(By.XPATH,".//following::intake-provider-info[@id='provider-info'][1]")        
            print(providerSection.text.lower())
            if 'invalid address' in providerSection.text.lower():
                addnewPrv = prv_section.find_element(By.XPATH,".//following::intake-provider-info[1]//button[normalize-space()='Add new Provider']")
                addnewPrv.click()

                wait = WebDriverWait(driver,5)
                firstNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-first-name-general-input")))
                lastNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-last-name-general-input")))
                FacNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-provider-name-general-input")))
                addr1Prv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-address-1-general-input")))
                addr2Prv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-address-2-general-input")))
                cityPrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-city-general-input")))
                statePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-state-select-input")))
                zipPrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-zip-code-zip-code-input")))

                firstNamePrv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", firstNamePrv)
                firstNamePrv.send_keys(providerFirst)

                lastNamePrv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", lastNamePrv)
                lastNamePrv.send_keys(providerLast)

                FacNamePrv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", FacNamePrv)
                FacNamePrv.send_keys(providerName)

                addr1Prv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", addr1Prv)
                addr1Prv.send_keys(providerAddr)

                addr2Prv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", addr2Prv)
                addr2Prv.send_keys("")

                cityPrv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", cityPrv)
                cityPrv.send_keys(providerCity)

                # stateAtty.clear()
                selPrvState = Select(statePrv)
                state_text = normalize_state_for_dropdown(providerState)
                if state_text:
                    selPrvState.select_by_visible_text(state_text)

                zipPrv.clear()
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", zipPrv)
                zipPrv.send_keys(providerZip)

                # prvAddrValidated = ValidateAddrPrv(prv_section)
            prvAddrValidated = ValidateAddrPrv(prv_section)
            providerSection = prv_section.find_element(By.XPATH,".//following::intake-provider-info[@id='provider-info'][1]")
           
            try:
                providerValidateAddrError = providerSection.find_element(By.XPATH,".//span[normalize-space()='Failed to find valid address with Google Maps'] ")
                                                                    #  "or normalize-space()='Failed to find valid address with Google Maps'")
            except:
                providerValidateAddrError = False
                pass
            
            def ExtractPrvName(section):
                try:
                    root = WebDriverWait(driver,3).until(EC.presence_of_element_located((By.ID,"provider-info")))

                    heading = WebDriverWait(root,3).until(EC.presence_of_element_located((By.CSS_SELECTOR,"div.panel-heading")))
                    HeaderName = (heading.get_attribute("innerText") or "").strip()
                    print(HeaderName)
                    # headers = section.find_elements(By.XPATH,
                    #                             (
                    #                                 # ".//div[contains(@class,'panel-heading') or contains(@class,'card-header')]"
                    #                             ".//following::div["
                    #                             " (contains(@class,'panel-heading') or contains(@class,'card-header'))"
                    #                             " and ancestor::intake-attorney-info"
                    #                             "][1]"
                    #                             )
                    #                             )   #./following-sibling::intake-attorney-info[1]
                    # if not headers:
                    #     return None
                    if not HeaderName:
                        return None
                    return HeaderName.strip()
                except TimeoutException:
                    return None
                
            def DoPrvSearch(section):

                info = section.find_element(By.XPATH,".//following::intake-provider-info[1]")
                searcPrv = info.find_element(By.XPATH,".//search-form-template[@searchtitle='Search Provider']"
                                                        "//i[contains(@class,'fa-search')]")
                searcPrv.click()

                dialogForm = WebDriverWait(driver,5).until(
                    EC.visibility_of_element_located((By.XPATH,"//h1[normalize-space()='Search Provider']"
                                                      "/ancestor::div[contains(@class,'modal-dialog')]"))
                )

                if providerName and (not providerLast and not providerFirst):
                    PrvFacName = dialogForm.find_element(By.ID,"intake-provider-search-facility-name-general-input")
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", PrvFacName)
                    PrvFacName.clear()
                    PrvFacName.send_keys(providerName)
                    # isFacility = True
                elif providerLast or providerFirst:
                    PrvFName = dialogForm.find_element(By.ID,"intake-provider-search-facility-name-general-input")
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", PrvFName)
                    PrvFName.clear()
                    PrvFName.send_keys(providerFirst)
                    time.sleep(1)
                    PrvLName = dialogForm.find_element(By.ID,"intake-provider-search-last-name-general-input")
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", PrvLName)
                    PrvLName.clear()
                    PrvLName.send_keys(providerLast)
                    time.sleep(1)
                PrvZipCode = dialogForm.find_element(By.ID,"intake-provider-search-zip-code-general-input")
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", PrvZipCode)
                PrvZipCode.clear()
                PrvZipCode.send_keys(providerZip)
                time.sleep(1)    

                Searchbtn = dialogForm.find_element(By.XPATH,".//button[@type='button' and normalize-space()='Search']")
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", Searchbtn)
                Searchbtn.click()
                time.sleep(3)

                resultCount = wait_for_attorney_search_results(driver)
                if resultCount >= 1:
                    notify("Notice","For Manual Process. Please validate the result.")
                else:
                    def askUserContinue():
                        import tkinter as tk
                        from tkinter import messagebox
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost',True)
                        answer = messagebox.askyesno("User Confirmation","No Results found. Do you want to add Provider Manually?\nSelect Yes if bot will add provider. \nSelect No if the user will manually search for the provider.")
                        if answer:
                            return True
                        else:
                            return False
                        
                    botStop = askUserContinue()
                    if botStop:
                        closeModal = dialogForm.find_element(By.XPATH,".//span[contains(@class,'close-button')]")
                        closeModal.click()
                        time.sleep(3)
                        # addnewPrv = prv_section.find_element(By.XPATH,".//button[normalize-space()='Add new Provider']")
                        addnewPrv = prv_section.find_element(By.XPATH,".//following::intake-provider-info[1]//button[normalize-space()='Add new Provider']")
                        addnewPrv.click()

                        wait = WebDriverWait(driver,5)
                        firstNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-first-name-general-input")))
                        lastNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-last-name-general-input")))
                        FacNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-provider-name-general-input")))
                        addr1Prv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-address-1-general-input")))
                        addr2Prv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-address-2-general-input")))
                        cityPrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-city-general-input")))
                        statePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-state-select-input")))
                        zipPrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-zip-code-zip-code-input")))

                        firstNamePrv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", firstNamePrv)
                        firstNamePrv.send_keys(providerFirst)

                        lastNamePrv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", lastNamePrv)
                        lastNamePrv.send_keys(providerLast)

                        FacNamePrv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", FacNamePrv)
                        FacNamePrv.send_keys(providerName)

                        addr1Prv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", addr1Prv)
                        addr1Prv.send_keys(providerAddr)

                        addr2Prv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", addr2Prv)
                        addr2Prv.send_keys("")

                        cityPrv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", cityPrv)
                        cityPrv.send_keys(providerCity)

                        # stateAtty.clear()
                        selPrvState = Select(statePrv)
                        state_text = normalize_state_for_dropdown(providerState)
                        if state_text:
                            selPrvState.select_by_visible_text(state_text)

                        zipPrv.clear()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", zipPrv)
                        zipPrv.send_keys(providerZip)

                        prvAddrValidated = ValidateAddrPrv(prv_section)
                    else:
                        notify("Notice","Bot Manual Stop for User Search")

        wait = WebDriverWait(driver,3)
        if not prvAddrValidated and not providerValidateAddrError:
            if providerLast or providerName:
                prvCheckName = ExtractPrvName(prv_section)
                checkPrvFac = "N/A"
                checkPrvLast = "N/A"
                checkPrvFirst= "N/A"
                try:
                    firstNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-first-name-general-input")))
                    lastNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-last-name-general-input")))
                    FacNamePrv = wait.until(EC.visibility_of_element_located((By.ID,"intake-provider-provider-name-general-input")))
                    checkPrvFirst = firstNamePrv.get_attribute("value")
                    checkPrvLast = lastNamePrv.get_attribute("value")
                    checkPrvFac = FacNamePrv.get_attribute("value")
                except: pass
                

                #edited already 3/4/26
                #if not prvCheckName:
                if (not prvCheckName and not (checkPrvFac or checkPrvFirst or checkPrvLast)) or prvCheckName != None: 
                    DoPrvSearch(prv_section)
                if(checkPrvFac != "N/A" or(checkPrvLast != "N/A" and checkPrvFirst != "N/A")) and prvCheckName:
                    DoPrvSearch(prv_section)
        elif not prvAddrValidated and providerValidateAddrError:
            notify("Manual Process Stopper","Manual Search or Add Provivider Details.\nClick Ok once Provider is Validated and Added.")

                                
        # Attachment: upload first file in folder (if any)
        try:
            files = glob.glob(os.path.join(ATTACHMENT_FOLDER, "*"))
            if not files:
                raise FileNotFoundError(f"No file found in {ATTACHMENT_FOLDER}")
            file_to_upload = files[0]
            print("Attaching:", file_to_upload)
    
            upload_input_xpath = (
                "/html/body/my-app/div/div/div/ng-component/div[2]/loading-section/div[1]/div/form/form-template/div/div/div/"
                "intake-attachments/form-section-template/section/div/div/form/kendo-upload/div/div[1]/input"
            )
            upload_input = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, upload_input_xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", upload_input)
            time.sleep(1)
            upload_input.send_keys(file_to_upload)
        except Exception as ex:
            print(f"Attachment step skipped/failed: {ex}")


        wait = WebDriverWait(driver, 3)
        btnCustDefined = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(@class,'btn') and contains(@class,'btn-link') and "
            "contains(normalize-space(.), 'Liberty Mutual Commercial Market') and "
            "contains(normalize-space(.), '20 fields')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btnCustDefined)
        btnCustDefined.click()

        dateOfAppointment = wait.until(EC.element_to_be_clickable((By.XPATH,
                                                                   "//field-label[normalize-space()='Date of First Appointment']"
                                                                   "/following::input[@type='text'][1]"
                                                                   )))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", dateOfAppointment)
        dateAppointmentVal = (dateOfAppointment.get_attribute("value") or "").strip
        if not dateAppointmentVal:
            dateOfAppointment.click()
            dateOfAppointment.clear()
            dateOfAppointment.send_keys(dataRef['nextApptDate'])
            time.sleep(0.5)
        ClaimIdentifier =  wait.until(EC.element_to_be_clickable((By.ID,"intake-customer-specific-field-fields--Claim Identifier-text-general-input")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ClaimIdentifier)
        ClaimIdentifierVal = (ClaimIdentifier.get_attribute("value") or "").strip
        if not ClaimIdentifierVal:
            ClaimIdentifier.click()
            ClaimIdentifier.clear()
            ClaimIdentifier.send_keys(dataRef['claimID'])

        if "goodyear tire & rubber co" in dataRef['customer'].lower():

            wait = WebDriverWait(driver, 3)
            btnEmpDefined = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//button[contains(@class,'btn') and contains(@class,'btn-link') and "
                "contains(normalize-space(.), 'GOODYEAR TIRE & RUBBER CO') and "
                "contains(normalize-space(.), '4 fields')]"
            )))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btnEmpDefined)
            btnEmpDefined.click()
            time.sleep(0.5)

            GOODYEAR_FACILITIES = [
                "PL0153 Lawton",
                "RE Retail Stores",
                "PL0133 Topeka",
                "CT Commercial Tire Centers",
                "CP0001 Texarkana",
                "PL0126 Danville",
                "PL0161 Fayetteville",
                "PL0155 Asheboro",
                "CP0016 Tupelo",
                "PL0130 Social Circle",
                "PL0131 Gadsden",
                "PL0933 Akron",
                "CP0018 Findlay",
                "CH0148 Bayport",
                "PL0129 Union City",
                "MS9999 Mileage Sales",
                "MS9999 Lake Buena Vista",
                "MS9999 Sun Valley",
                "MS9999 Chatsworth",
                "MS9999 El Monte",
                "PL0170 Kingman",
                "CH0141 Houston",
                "CH0137 Niagara Falls",
                "EP0112 Saint Marys",
                "ML1286 Eglin Air Force Base",
            ]

            def GoodyearSearchFacilityName(special_instructions: str) -> str:
                if not special_instructions:
                    return ""
                text = special_instructions.lower()
                for item in GOODYEAR_FACILITIES:
                    if item.lower() in text:
                        return item
                return ""
            
            def _norm_ws(s: str) -> str:
                return re.sub(r"\s+", " ", (s or "")).strip().lower()
            

            
            def select_goodyear_facility_or_leave_blank(
                driver,
                special_instructions: str,
                select_id: str = "intake-customer-specific-field-fields--Facility-select-input",
                timeout: int = 20,
            ) -> str:
                """
                If a match is found, selects it and returns the selected option text.
                If no match is found, leaves the field unchanged (blank) and returns "".
                """
                facility_token = GoodyearSearchFacilityName(special_instructions)

                wait = WebDriverWait(driver, timeout)
                sel_el = wait.until(EC.presence_of_element_located((By.ID, select_id)))
                sel = Select(sel_el)

                if not facility_token:
                    providerCity = dataRef['providerCity']
                    for opt in sel.options:
                        drpMatchFacility = opt.text.strip()
                        if providerCity.lower() in drpMatchFacility.lower():
                            facility_token = drpMatchFacility
                            break

                if not facility_token:
                    return ""
            
               
            
                token_n = _norm_ws(facility_token)
            
                # Select only when we find a matching option
                for opt in sel.options:
                    if token_n in _norm_ws(opt.text):
                        sel.select_by_visible_text(opt.text)
                        return opt.text
            
                # No match -> do nothing (leave as-is / blank)
                return ""
            
            selected = select_goodyear_facility_or_leave_blank(driver,dataRef['specialInstructions'])
            if not selected:
                notify("Goodyear Employer Defined Field - Facility","No matching Facility from Dropdown.")
    
        time.sleep(2)
        notify("Notice", "Stopped for Manual Validation before Completing Task.")
    
        # Complete Task (only auto-click for specific claimant guard)
        try:
            complete_btn = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
                By.XPATH,
                "/html/body/my-app/div/div/div/ng-component/div[1]/div/div[3]/span/button[3]"
            )))
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", complete_btn)
            complete_btn.click()
        except Exception:
            pass

        time.sleep(15)
    except Exception as ex:
        exc_type, exc_obj, tb = sys.exc_info()
        print(f"error occurred: {ex} (line {tb.tb_lineno})")
 
# ---------- Entrypoint ----------
def main(customer_name: str, claimant_name: str,dataRef: dict):
    driver = None
    try:
        # pprint(dataRef)
        driver = create_driver()
        login(driver)
        validate_and_complete_task(driver, customer_name, claimant_name,dataRef)
    except Exception as ex:
        exc_type, exc_obj, tb = sys.exc_info()
        print(f"error occurred: {ex} (line {tb.tb_lineno})")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
 
 
if __name__ == "__main__":
    # Example single-run (safe to call many times from your UI)
#     dataRef = {'AccidentDesc': 'UNKNOWN',
#  'InjuryDesc': 'UNKNOWN INJURY TO UNKNOWN BACK, UNKNOWN\n'
#                'KNEE, UNKNOWN LEG, UNKNOWN FOOT',
#  'addressLine1': '7654 LAUREL CANYON BLVD',
#  'addressLine2': 'APT 214',
#  'adjuster': 'Lawrence, Emeli I',
#  'bodyPart': 'Multiple Body Parts',
#  'city': 'NORTH HOLLYWOOD',
#  'claimNumber': 'WC648D18242',
#  'claimStateAbbr': 'CA',
#  'claimStateFull': 'California',
#  'claimantAttyAddr1': '427 W. Colorado St.',
#  'claimantAttyAddr2': 'Ste 106',
#  'claimantAttyCity': 'Glendale',
#  'claimantAttyName': 'Jonathan D Rosen',
#  'claimantAttyPhone': '818-500-0233',
#  'claimantAttyState': 'CA',
#  'claimantAttyZip': '91204',
#  'claimantFirst': 'ROSALBA',
#  'claimantFull': 'ROJAS,ROSALBA',
#  'claimantLast': 'ROJAS',
#  'customer': 'GLOBAL BUILDING SERVICES, INC.',
#  'dob': '04/15/1975',
#  'doi': '02/01/2021',
#  'gender': 'Male',
#  'injuryCause': 'Other - Miscellaneous, NOC',
#  'injuryType': 'All Other Specific Injuries, NOC',
#  'nextApptDate': '11/20/2025',
#  'nextApptTime': '10:00 AM',
#  'phoneNumber': '818-564-3588',
#  'providerAddr': '1127 Wilshire Blvd #508',
#  'providerCity': 'Los Angeles',
#  'providerFirst': '',
#  'providerLast': '',
#  'providerName': 'Farsa Chiropractic',
#  'providerPhone': '818-886-1406',
#  'providerState': 'CA',
#  'providerZip': '90017',
#  'refSource': '',
#  'refTypeInList1': False,
#  'refTypeInList2': False,
#  'referralNumber': '24126247',
#  'referralType': '',
#  'specialInstructions': '',
#  'state': 'CA',
#  'zip': '91605',
#  'refType':'Medical',
#  'serviceType' : 'Medical Full',
#  'caseObj': 'Coordination of Care/Services'
#  }
# main("GLOBAL BUILDING SERVICES", "ROSALBA ROJAS",dataRef)
    dataRef = {'AccidentDesc': 'EMPLOYEE WAS IN THE GANTRY ACCESS AREA OF\n'
                 'MACHINE WHEN THE ROBOT CAME DOWN ON HIS HEAD.',
 'CaseObj': 'Coordination of Care/Services',
 'InjuryDesc': 'CRUSHING OF HEAD',
 'ServiceType': 'Medical Full',
 'addressLine1': 'C/O JOHN DEVRIES',
 'addressLine2': '41 SPRING LAKE DRIVE',
 'adjAddr1': '2000 Westwood Dr.',
 'adjAddr2': '',
 'adjAddrFull': '2000 Westwood Dr. Wausau, WI 54401-7881',
 'adjAddrMail': 'P.O. Box 8016, Wausau, WI 54402-8016',
 'adjCity': 'Wausau',
 'adjEmail': 'BRENDA.MARVIN@LIBERTYMUTUAL.COM',
 'adjPhone': '309-621-7136 ',
 'adjState': 'WI',
 'adjZip': '54401',
 'adjuster': 'Brenda J Marvin',
 'bodyPart': 'Multiple Body Parts',
 'city': 'OXFORD',
 'claimID': '137242850',
 'claimNumber': 'WC868D27989',
 'claimStateAbbr': 'MI',
 'claimStateFull': 'Michigan',
 'claimType': 'Workers Compensation',
 'claimantAttyAddr1': '1121 N. Michigan Avenue',
 'claimantAttyAddr2': '',
 'claimantAttyCity': 'Saginaw',
 'claimantAttyName': 'Michael Doud',
 'claimantAttyPhone': '989-401-8778  18778',
 'claimantAttyState': 'MI',
 'claimantAttyZip': '48602',
 'claimantFirst': 'BRAD',
 'claimantFull': 'DEVRIES,BRAD E',
 'claimantLast': 'DEVRIES',
 'claimantSSN': '***-**-5037',
 'customer': 'Baldauf Enterprises Inc',
 'dob': '08/16/1975',
 'doi': '10/31/2022',
 'dxCode': 'R41.844',
 'employerContactName': '',
 'gender': 'Male',
 'injuryCause': 'Machine or Machinery',
 'injuryType': 'Crushing',
 'languageSpoken': 'English',
 'ncmContactName': '',
 'nextApptDate': '03/16/2026',
 'nextApptTime': '',
 'phoneNumber': '989-482-8304',
 'providerAddr': 'Lighthouse Inc., 1655 E. Caro Rd.',
 'providerCity': 'Caro',
 'providerFirst': '',
 'providerLast': '',
 'providerName': 'Lighthouse - Contact is Brandy Bly',
 'providerPhone': '989-673-2500',
 'providerState': 'MI',
 'providerZip': '48723',
 'refSource': '',
 'refType': 'Medical',
 'refTypeInList1': False,
 'refTypeInList2': False,
 'referralNumber': '24616292',
 'referralType': 'Full Case Management',
 'specialInstructions': '**Assigned nurse must contact claim case manager '
                        'and/or tele NCM to discuss/confirm referral\n'
                        'instructions. *\n'
                        'ASSIGNMENT TYPE:\n'
                        'Onsite NCM: [X ] Full\n'
                        'Provider Name: Lighthouse - Contact is Brandy Bly\n'
                        'Phone #: 989-673-2500\n'
                        'Address of Appt. location: Lighthouse Inc., 1655 E. '
                        'Caro Rd., Caro, MI 48723\n'
                        'Appt. Date: Time: Neuropsych eval set for 3/16 '
                        'followed by FCE\n'
                        'Employer name and contact: N/A - No contact needed\n'
                        'Phone #: N/A\n'
                        'SSIs: N/A\n'
                        'Atty Permission: [X ] No Atty\n'
                        'Atty name: N/A\n'
                        'Phone #: N/A\n'
                        'COMPENSABLE BODY PART(S) & DIAGNOSIS: Injury '
                        'Description:\n'
                        'On 08/15/2024, Brad Devries, a 47-year-old machine '
                        'operator, sustained catastrophic injuries when struck '
                        'by a\n'
                        'descending robotic arm in the battery cage of a '
                        'molding machine, resulting in a crushed skull; the '
                        'incident was\n'
                        'unwitnessed and the lockout/tagout system was '
                        'disabled, with speculation he was repositioning raw '
                        'material.\n'
                        'Body Parts & Compensability:\n'
                        'Accepted body parts include the skull, facial bones, '
                        'orbits, nasal and sinus structures, teeth, mandible, '
                        'zygomatic arch,\n'
                        'pterygoid plate, and brain (TBI), with additional '
                        'accepted conditions of mental/cognitive impairment, '
                        'urinary incontinence,\n'
                        'and vision/hearing deficits; all listed injuries are '
                        "compensable under workers' compensation.\n"
                        'WORK STATUS: Off work - unable to return to work.',
 'state': 'MI',
 'zip': '48371'}
    main("Baldauf Enterprises Inc", "BRAD DEVRIES",dataRef)



