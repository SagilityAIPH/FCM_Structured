"""Shared legacy UI steps. Invoke through subject_line_flow, not directly."""

def CreateSubjectLineBuilder(app = None):
    try:
        global isManualEntered
        global botStop
        global data
        global correctZipCode
        botStop = True
        main = Desktop(backend="uia").window(title_re=r"Referral Routing System*",control_type="Window")
        focus_control(main)
        # pid = main.element_info.process_id
        allData = {}
        grid = main.child_window(auto_id="dgWorkWindow",control_type="Table")#.wrapper_object()
        # Selecting from DatagridView
        # try:
        #     rowtbCount = grid.iface_grid.CurrentRowCount
        #     coltbCount = grid.iface_grid.CurrentColumnCount
        #     print(f"Rpws: {rowtbCount} Col:{coltbCount}")
        # except Exception as e:
        #     print(e)
        
        # rowsSelection = grid.descendants(control_type="DataItem")
        # if not rowsSelection:
        #     raise Exception("No Rows found in Grid")
        # rowsSelection = rowsSelection[0]
        # cells = rowsSelection.children()
        # if len(cells) <= 4:
        #     cells = rowsSelection.descendants()

        # cell = cells[4]
        # print(repr(cell.window_text()))

        cell_el = grid.child_window(title="Claimant Row 0",control_type="Edit").wrapper_object()
        ClaimantRRS = cell_el.iface_value.CurrentValue

        # cell_el = grid.iface_grid.GetItem(0,4)
        # cell = UIAWrapper(UIAElementInfo(cell_el))
        # ClaimantRRS = cell.iface_value.CurrentValue
        FNameRRS = re.split(r"\s+",ClaimantRRS)[0]
        # print(FNameRRS)
        cell_el.double_click_input()

        emaiDisplay = Desktop(backend="uia").window(title_re=r"Email Display*",control_type="Window")
        focus_control(emaiDisplay)

        grid = emaiDisplay.child_window(auto_id="dgAttach",control_type="Table")
        AttachRow = grid.iface_grid.CurrentRowCount

        for r in range(AttachRow):
            # cell_el = grid.iface_grid.GetItem(r,2)
            # cell = UIAWrapper(UIAElementInfo(cell_el))

            cell = grid.child_window(title=f"Filename Row {r}, Not sorted.", control_type="Edit").wrapper_object()


            AttachmentName = cell.iface_value.CurrentValue
            Attachment = AttachmentName.lower()
            has_11_letter_w = bool(re.search(r"\bw\w{10}\b", Attachment))


            # if FNameRRS.lower() in AttachmentName.lower():
            if not "icasemanager" in Attachment and ("," in Attachment or has_11_letter_w):
                # print(AttachmentName)
                focus_control(emaiDisplay)
                cell.double_click_input()
                allData = OpenPDFAndCaptureData(AttachmentName)
                print(f'Fetching Information if Referral PDF.')
                pprint(allData)
                #INSERT RETRIEVAL OF DATA

                break
        # def LMContinentalTire(allData:dict):
        if "auto" in allData['claimType'].lower() and "continental tire" in allData['customer'].lower() and "mi" in allData['claimStateAbbr'].lower() :
            allData['ServiceType'] ="Medical Task"
            allData['refType'] ="Task"
            allData['CaseObj'] = "MI MCCA Attendant Care"

        #Goodyear Tire with Facility
        GYFacility = GoodyearSearchFacilityName(allData['specialInstructions'])

        #Comcast
        # if "comcast" in allData['customer'].lower():
        #     notify("Notice","For Manual Process. Refer to Standard Intake Rules Guidelines for Comcast.")
        #     botStop=True
        #     sys.exit()
        
        #Genetech
        # if "genetech" in allData['customer'].lower():
        #     notify("Notice","For Manual Process. Refer to Standard Intake Rules Guidelines for Genetech.")
        #     botStop=True
        #     sys.exit()
        


        #Test1
        # allData['providerZip']=""
        missing = get_validation_missing(allData)
        def _click_first_row_if_any(prvType, FacilityName, ProvFirst, ProvLast):
                global isManualEntered
                # FacilityName = "Roanoke Orthopedic"
                try:
                    grid = ups.child_window(auto_id="dgResults", control_type="Table")
                    rows = int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)
            
                    if rows <= 0:
                        isManualEntered = False
                        return False
            
                    RealAddr = f"{allData['providerAddr']} {FacCity} {FacState} {FacZip}"
                    RealAddress = expand_suffix_long(RealAddr)
                    realPhone = format_phone_us(FacPhoneNumber)
            
                    # Read all row data first
                    row_data = []
                    for r in range(rows):
                        print(f'Fetching Result Row {r}. Total Row {rows}')
                        try:
                            name_cell = grid.child_window(title=f"Name Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                            ResultName = name_cell.iface_value.CurrentValue
                            print(ResultName)
                            addr_cell = grid.child_window(title=f"Address Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                            ResultAddress = addr_cell.iface_value.CurrentValue
            
                            phone_cell = grid.child_window(title=f"Phone Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                            ResultPhone = phone_cell.iface_value.CurrentValue
            
                            TempAddress = expand_suffix_long(ResultAddress)
                            ComparisonResult = addressMatch(TempAddress, RealAddress)
            
                            tempPhone = format_phone_us(ResultPhone)
            
                            phone_match = False
                            if realPhone and tempPhone:
                                phone_match = (realPhone == tempPhone)

                            similarity = difflib.SequenceMatcher(
                            None, TempAddress.lower(), RealAddress.lower()
                            ).ratio()
            
                            row_data.append({
                                "row": r,
                                "name": ResultName or "",
                                "address": ResultAddress or "",
                                "phone": ResultPhone or "",
                                "address_match": ComparisonResult,
                                "phone_match": phone_match,
                                "similarity":similarity
                            })
                        except Exception:
                            continue
            
                    # If only one row exists, you can still apply your logic first
                    # instead of blindly selecting it.
                    # ------------------------------
                    # PASS 1: Strong name match + address + phone
                    # ------------------------------
                    print(f'Validating fetched infomation from Provider Search')
                    for item in row_data:
                        # print(item["similarity"])
                        # print(item["similarity"] >= 0.76)
                        if not (item["address_match"] or item["similarity"] >= 0.76):
                            continue
                        if not item["phone_match"]:
                            continue

                        if prvType == "fac":
                            if _facility_name_strong_match(FacilityName, item["name"]):
                                _click_select_row(grid, item["row"])
                                time.sleep(2)
                                btnSelect = ups.child_window(auto_id="btnSelect", control_type="Button").wrapper_object()
                                safe_click(btnSelect)
                                isManualEntered = True
                                return True
            
                        elif prvType == "prof":
                            if _provider_name_strong_match(ProvFirst, ProvLast, item["name"]):
                                _click_select_row(grid, item["row"])
                                time.sleep(2)
                                btnSelect = ups.child_window(auto_id="btnSelect", control_type="Button").wrapper_object()
                                safe_click(btnSelect)
                                isManualEntered = True
                                return True
            
                    # ------------------------------
                    # PASS 2: Loose name match + address + phone
                    # ------------------------------
                    for item in row_data:
                        # print(f'{item["similarity"]}')
                        # print(item["similarity"] >= 0.76)
                        if not (item["address_match"] or item["similarity"] >= 0.76):
                            continue
                        if not item["phone_match"]:
                            continue
            
                        if prvType == "fac":
                            
                            # if _facility_name_loose_match(FacilityName, item["name"]):
                                googlePrvName = prvGoogleSearch(item["name"])
                                if googlePrvName:
                                    # if _facility_name_loose_match(googlePrvName,item["name"]):
                                    _click_select_row(grid, item["row"])
                                    time.sleep(2)
                                    btnSelect = ups.child_window(auto_id="btnSelect", control_type="Button").wrapper_object()
                                    safe_click(btnSelect)
                                    isManualEntered = True
                                    return True
            
                        elif prvType == "prof":
                            looseCheck = _provider_name_loose_match(ProvFirst, ProvLast, item["name"])
                            if not looseCheck:
                                googlePrvName = prvGoogleSearch(item["name"])
                                if googlePrvName:
                                    # if _provider_name_loose_match(ProvFirst, ProvLast,item["name"]):
                                # prvGoogleSearch(item["name"])
                                    _click_select_row(grid, item["row"])
                                    time.sleep(2)
                                    btnSelect = ups.child_window(auto_id="btnSelect", control_type="Button").wrapper_object()
                                    safe_click(btnSelect)
                                    isManualEntered = True
                                return True
                            else:
                                _click_select_row(grid, item["row"])
                                time.sleep(2)
                                btnSelect = ups.child_window(auto_id="btnSelect", control_type="Button").wrapper_object()
                                safe_click(btnSelect)
                                isManualEntered = True
                                return True
            
                    isManualEntered = False
                    return False
            
                except Exception as e:
                    print(f"_click_first_row_if_any error: {e}")
                    isManualEntered = False
                    return False
                
        def run_provider_search():
            global isManualEntered
            FacilityLName = allData['providerLast']
            FacilityFName = allData['providerFirst']
            FacilityName  = allData['providerName']
            FacPhoneNumber = allData['providerPhone']
            FacCity = allData['providerCity']
            FacState = allData['providerState']
            FacZip = allData['providerZip']
            first = (FacilityFName or "").strip()
            last  = (FacilityLName or "").strip()
            fac   = (FacilityName  or "").strip()
            phone = (FacPhoneNumber or "").strip()
            city  = (FacCity or "").strip()
            state = (FacState or "").strip()
            zip_  = (FacZip or "").strip()

            isManualEntered = False
            firstAttempt = False
            facilityFirst = ""
            facility = " ".join(fac.strip().split())
            facilityWords = re.findall(r"[A-Za-z0-9&]+",facility)

            if not facilityWords:
                facilityFirst = ""
            elif facilityWords[0].upper() == "THE":
                facilityFirst = facilityWords[1] if len(facilityWords) > 1 else ""
            else:
                facilityFirst = facilityWords[0]

            if (tbZipVal or cbStateVal or tbCityVal or tbPhoneVal or tbFacilityVal or tbFirstVal or tbLastVal):
                _click_search()
                _wait_search_idle()
                count = _results_count()
                if count > 0:
                    if tbFacilityVal:
                        prvType = 'fac'
                        # if tbFacilityVal:
                            # fac = tbFacilityVal
                        SelectedPrvResult = firstAttempt = _click_first_row_if_any(prvType,fac,None,None)
                        if firstAttempt:
                            return count,SelectedPrvResult
                    else:
                        prvType = 'prof'
                        SelectedPrvResult = firstAttempt = _click_first_row_if_any(prvType,None,first,last)
                        if SelectedPrvResult:
                            return count,SelectedPrvResult

            # else:
                # 1) If Last+First both present, use them (with phone/city/state/zip)
            if fac and (not first and not last):
                count = _search_with(first=None, last=None, facility=facilityFirst,
                                    phone=phone, city=None, state=None, zip_=None)
                prvType = 'fac'
                if count <= 10:
                    SelectedPrvResult = firstAttempt = _click_first_row_if_any(prvType,facilityFirst,None,None)
                    if firstAttempt:
                        return count,SelectedPrvResult
            else:
                count = _search_with(first=first, last=last, facility=None,
                                    phone=phone, city=None, state=None, zip_=None)
                prvType = 'prof'
                if count <= 10:
                    SelectedPrvResult = firstAttempt = _click_first_row_if_any(prvType,None,first,last)
                    if firstAttempt:
                        return count,SelectedPrvResult
            # 2) Else if FacilityName present, use it (with phone/city/state/zip)
            if not firstAttempt:
                if fac and (not first and not last):
                    count = _search_with(first=None, last=None, facility=facilityFirst,
                                        phone=phone, city=city, state=state, zip_=zip_)
                    prvType = 'fac'
                    if count > 0:
                        SelectedPrvResult = _click_first_row_if_any(prvType,facilityFirst,None,None)
                        return count,SelectedPrvResult
                else:
                    count = _search_with(first=first, last=last, facility=None,
                                        phone=phone, city=city, state=state, zip_=zip_)
                    prvType = 'prof'
                    if count > 0:
                        SelectedPrvResult = _click_first_row_if_any(prvType,None,first,last)
                        return count,SelectedPrvResult
            # return 0,False
            return 0,False

        def run_provider_search_part():
                global isManualEntered

                # tbProviderLastExtract = ups.child_window(auto_id="tbProviderLastExtract", control_type="Edit").wrapper_object()
                # tbProviderLastExtractVal = (tbProviderLastExtract.iface_value.CurrentValue or "").strip()

                tbLast = ups.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
                tbLastVal = (tbLast.iface_value.CurrentValue or "").strip()
                # if tbLastVal:
                #     allData['providerLast'] = tbLastVal
                # elif tbProviderLastExtractVal:
                #     allData['providerLast'] = tbProviderLastExtractVal
                
                # tbProviderFirstExtract = ups.child_window(auto_id="tbProviderFirstExtract", control_type="Edit").wrapper_object()
                # tbProviderFirstExtractVal = (tbProviderFirstExtract.iface_value.CurrentValue or "").strip()
                tbFirst = ups.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
                tbFirstVal = (tbFirst.iface_value.CurrentValue or "").strip()
                # if tbFirstVal:
                #     allData['providerFirst'] = tbFirstVal
                # elif tbProviderFirstExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerFirst'] = tbProviderFirstExtractVal
                
                # tbProviderNameExtract = ups.child_window(auto_id="tbProviderNameExtract", control_type="Edit").wrapper_object()
                # tbProviderNameExtractVal = (tbProviderNameExtract.iface_value.CurrentValue or "").strip()
                tbFacility = ups.child_window(auto_id="tbFacility", control_type="Edit").wrapper_object()
                tbFacilityVal = (tbFacility.iface_value.CurrentValue or "").strip()
                # if tbFacilityVal:
                #     allData['providerName'] = tbFacilityVal
                # elif tbProviderNameExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerName'] = tbProviderNameExtractVal
                
                # tbAddressExtract = ups.child_window(auto_id="tbAddressExtract", control_type="Edit").wrapper_object()
                # tbAddressExtractVal = (tbAddressExtract.iface_value.CurrentValue or "").strip()
                # if tbAddressExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerAddr'] = tbAddressExtractVal
                
                # tbPhoneExtract = ups.child_window(auto_id="tbPhoneExtract", control_type="Edit").wrapper_object()
                # tbPhoneExtractVal = (tbPhoneExtract.iface_value.CurrentValue or "").strip()
                tbPhone = ups.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
                tbPhoneVal = (tbPhone.iface_value.CurrentValue or "").strip()
                # if tbPhoneVal:
                #     allData['providerPhone'] = tbPhoneVal
                # elif tbPhoneExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerPhone'] = tbPhoneExtractVal
                
                # tbCityExtract = ups.child_window(auto_id="tbCityExtract", control_type="Edit").wrapper_object()
                # tbCityExtractVal = (tbCityExtract.iface_value.CurrentValue or "").strip()
                tbCity = ups.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
                tbCityVal = (tbCity.iface_value.CurrentValue or "").strip()
                # if tbCityVal:
                #     allData['providerCity'] = tbCityVal
                # elif tbCityExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerCity'] = tbCityExtractVal
                
                # tbStateExtract = ups.child_window(auto_id="tbStateExtract", control_type="Edit").wrapper_object()
                # tbStateExtractVal = (tbStateExtract.iface_value.CurrentValue or "").strip()
                cbState = ups.child_window(auto_id="cbState", control_type="ComboBox").wrapper_object()
                cbStateVal = (cbState.iface_value.CurrentValue or "").strip()
                # if cbStateVal:
                #     allData['providerState'] = cbStateVal
                # elif tbStateExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerState'] = tbStateExtractVal
                
                # tbZipExtract = ups.child_window(auto_id="tbZipExtract", control_type="Edit").wrapper_object()
                # tbZipExtractVal = (tbZipExtract.iface_value.CurrentValue or "").strip()
                tbZip = ups.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
                tbZipVal = (tbZip.iface_value.CurrentValue or "").strip()
                # if tbZipVal:
                #     allData['providerZip'] = tbZipVal
                # elif tbZipExtractVal:
                #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
                #     allData['providerZip'] = tbZipExtractVal

                FacilityLName = allData['providerLast']
                FacilityFName = allData['providerFirst']
                FacilityName  = allData['providerName']
                FacPhoneNumber = allData['providerPhone']
                FacCity = allData['providerCity']
                FacState = allData['providerState']
                FacZip = allData['providerZip']
                first = (FacilityFName or "").strip()
                last  = (FacilityLName or "").strip()
                fac   = (FacilityName  or "").strip()
                phone = (FacPhoneNumber or "").strip()
                city  = (FacCity or "").strip()
                state = (FacState or "").strip()
                zip_  = (FacZip or "").strip()

                isManualEntered = False
                firstAttempt = False
                facilityFirst = ""
                facility = " ".join(fac.strip().split())
                facility = re.sub(r"[^A-Za-z0-9\s,\.\-]", "" ,facility)
                facility = re.sub(r"\s+", " " ,facility).strip()
                facility = re.sub(r"[-\s]+$", " " ,facility).strip()
                # print(facility)
                facilityWords = re.findall(r"[A-Za-z0-9&]+",facility)


                if not facilityWords:
                    facilityFirst = ""
                elif facilityWords[0].upper() == "THE":
                    facilityFirst = facilityWords[1] if len(facilityWords) > 1 else ""
                else:
                    facilityFirst = facilityWords[0]

                if (tbZipVal or cbStateVal or tbCityVal or tbPhoneVal or tbFacilityVal or tbFirstVal or tbLastVal):
                    _click_search()
                    _wait_search_idle()
                    count = _results_count()
                    if count > 0:
                        if tbFacilityVal:
                            prvType = 'fac'
                            SelectedPrvResult = firstAttempt = _click_first_row_if_any(prvType,fac,None,None)
                            if firstAttempt:
                                return count,SelectedPrvResult
                        else:
                            prvType = 'prof'
                            SelectedPrvResult = firstAttempt = _click_first_row_if_any(prvType,None,first,last)
                            if SelectedPrvResult:
                                return count,SelectedPrvResult

                # 1) If Last+First both present, use them (with phone/city/state/zip)
                if fac and (not first and not last):
                    count = _search_with(first=None, last=None, facility=facility,
                                        phone=phone, city=None, state=None, zip_=None)
                    prvType = 'fac'
                    if count <= 10:
                        firstAttempt,NewResultName,NewResultAddr,NewResultPhone = CheckPrvFromList(prvType,facility,None,None)
                        if firstAttempt:
                            return count,NewResultName,NewResultAddr,NewResultPhone
                else:
                    count = _search_with(first=first, last=last, facility=None,
                                        phone=phone, city=None, state=None, zip_=None)
                    prvType = 'prof'
                    if count <= 10:
                        firstAttempt,NewResultName,NewResultAddr,NewResultPhone = CheckPrvFromList(prvType,None,first,last)
                        if firstAttempt:
                            return count,NewResultName,NewResultAddr,NewResultPhone
                # 2) Else if FacilityName present, use it (with phone/city/state/zip)
                if not firstAttempt:
                    if fac and (not first and not last):
                        count = _search_with(first=None, last=None, facility=facility,
                                            phone=phone, city=city, state=state, zip_=zip_)
                        prvType = 'fac'
                        if count > 0:
                            firstAttempt,NewResultName,NewResultAddr,NewResultPhone = CheckPrvFromList(prvType,facility,None,None)
                            return count,NewResultName,NewResultAddr,NewResultPhone
                    else:
                        count = _search_with(first=first, last=last, facility=None,
                                            phone=phone, city=city, state=state, zip_=zip_)
                        prvType = 'prof'
                        if count > 0:
                            firstAttempt,NewResultName,NewResultAddr,NewResultPhone =CheckPrvFromList(prvType,None,first,last)
                            return count,NewResultName,NewResultAddr,NewResultPhone
                return 0,NewResultName,NewResultAddr,NewResultPhone

        #Add Search RRS
        if missing:
            print(f'Missing Provider Info. Searching thru RRS Provider Search.')
            focus_control(emaiDisplay)
            SubjectLineBuilder = emaiDisplay.child_window(auto_id="btnSubjectSearch",control_type="Button").wrapper_object()
            focus_control(SubjectLineBuilder)
            safe_click(SubjectLineBuilder)

            dlg = Desktop(backend="uia").window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
            dlg.wait("exists enabled visible ready",timeout=120,retry_interval=1)
            focus_control(dlg)

            tbCustomer = dlg.child_window(auto_id="tbCustomer", control_type="Edit").wrapper_object()
            tbCustomer.iface_value.SetValue("Liberty Mutual Commercial Market")
            time.sleep(3)

            rbProvider = dlg.child_window(auto_id="rbProvider", control_type="RadioButton").wrapper_object()
            rbProvider.select()
            time.sleep(3)
            # pbProvider (Pane Magnifying Glass)
            pbProvider = dlg.child_window(auto_id="pbProvider",control_type="Pane").wrapper_object()
            safe_click(pbProvider)
            time.sleep(3)
            #ADD Searching here!
            desk = Desktop(backend="uia")
            owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
            owner.wait('exists',timeout=5.0)
            ups = owner.child_window(auto_id="frmUnityProviderLM",control_type="Window")
            ups.wait('exists',timeout=5.0)
            
            
            #Add Search Prv
            def CheckPrvFromList(prvType,FacilityName,ProvFirst,ProvLast):
                try:
                    grid = ups.child_window(auto_id="dgResults", control_type="Table")#.wrapper_object()
                    rows = int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)
                    if rows >= 1:
                        for r in range(rows):
                            # cell_el = grid.iface_grid.GetItem(r,2)
                            # cell = UIAWrapper(UIAElementInfo(cell_el))
                            cell = grid.child_window(title=f"Name Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                            ResultName = cell.iface_value.CurrentValue
                            
                            if ProvFirst or ProvLast:
                                RealName = f"{ProvFirst} {ProvLast}"
                            else:
                                RealName = f"{FacilityName}"
                            CompareNameResult = RealName in ResultName


                            # cell_el = grid.iface_grid.GetItem(r,3)
                            # cell = UIAWrapper(UIAElementInfo(cell_el))
                            cell = grid.child_window(title=f"Address Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                            ResultAddress = cell.iface_value.CurrentValue
                            RealAddr = f"{allData['providerAddr']} {allData['providerCity']} {allData['providerState']} {allData['providerZip']}"
                            # print(RealAddr)
                            TempAddress = expand_suffix_long(ResultAddress)
                            RealAddress = expand_suffix_long(RealAddr)
                            ComparisonResult = addressMatch(TempAddress,RealAddress)

                            if allData['providerPhone']:
                                # cell_el = grid.iface_grid.GetItem(r,4)
                                # cell = UIAWrapper(UIAElementInfo(cell_el))
                                cell = grid.child_window(title=f"Phone Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                                ResultPhone = cell.iface_value.CurrentValue
                                realPhone = format_phone_us(allData['providerPhone'])
                                tempPhone = format_phone_us(ResultPhone)
                                ComparePhoneResult = realPhone in tempPhone
                            else:
                                ResultPhone = None
                                ComparePhoneResult = False
                                
                            if (CompareNameResult and ComparisonResult):
                                return True  ,ResultName, ResultAddress,ResultPhone
                        return False,None,None,None
                except Exception:
                    pass
                return False,None,None,None
            
            def _get_edit(auto_id):
                return ups.child_window(auto_id=auto_id, control_type="Edit").wrapper_object()

            def _set_value(ctrl, value):
                try:
                    ctrl.iface_value.SetValue("")   # clear
                    if value:
                        ctrl.iface_value.SetValue(value)

                except Exception:
                    # Fallback to type_keys if needed
                    try:
                        focus_control(ctrl)
                        ctrl.type_keys("^a{BACKSPACE}")
                        if value:
                            ctrl.type_keys(value, with_spaces=True)
                    except Exception:
                        pass

            def _select_state(value):
                try:
                    cb = ups.child_window(auto_id="cbState", control_type="ComboBox").wrapper_object()
                    if value:
                        cb.select(value)
                    else:
                        try:
                            cb.select(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _click_search():
                btn = ups.child_window(auto_id="btnSearch", control_type="Button").wrapper_object()
                safe_click(btn)

            def _wait_search_idle(timeout=300.0):
                lbl = ups.child_window(auto_id="lblStatus", control_type="Text")
                end_t = time.monotonic() + timeout
                while time.monotonic() < end_t:
                    try:
                        w = lbl.wrapper_object()
                        if (not w.is_visible()) or ((w.window_text() or "").strip() == ""):
                            return True
                    except Exception:
                        return True
                    time.sleep(0.2)
                return False

            def _results_count():
                try:
                    grid = ups.child_window(auto_id="dgResults", control_type="Table").wrapper_object()
                    return int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)
                except Exception:
                    return 0
                
            def _fill_common_filters(phone, city, state, zip_):
                # Phone
                try: _set_value(_get_edit("tbPhone"), phone)
                except Exception: pass
                # City
                try: _set_value(_get_edit("tbCity"), city)
                except Exception: pass
                # State
                _select_state(state)
                # Zip
                try: _set_value(_get_edit("tbZip"), zip_)
                except Exception: pass

            def _clear_all_inputs():
                for eid in ("tbFirst","tbLast","tbFacility","tbPhone","tbCity","tbZip"):
                    try:
                        _set_value(_get_edit(eid), "")
                    except Exception:
                        pass
                _select_state(None)

            def _search_with(first=None, last=None, facility=None,
                            phone=None, city=None, state=None, zip_=None):
                """Populate fields, click Search, wait, return count."""
                
                # Names
                if first is not None:
                    try: _set_value(_get_edit("tbFirst"), first)
                    except Exception: pass
                if last is not None:
                    try: 
                        _set_value(_get_edit("tbLast"), last)
                        try:
                            _set_value(_get_edit("tbFacility"), "")
                        except Exception:
                            pass
                    except Exception: pass

                # Facility
                if facility is not None:
                    try: _set_value(_get_edit("tbFacility"), facility)
                    except Exception: pass
                # Common filters
                _fill_common_filters(phone, city, state, zip_)
                # Search
                _click_search()
                _wait_search_idle()

                return _results_count()
            
            
            
            
            rows_found,NewResultName,NewResultAddr,NewResultPhone = run_provider_search_part()
            btn = ups.child_window(auto_id="btnClose", control_type="Button").wrapper_object()
            safe_click(btn)

            tempAddr1 = ""
            tempAddr2 = ""
            tempCity = ""
            tempState = ""
            tempZip = ""
            # providerPhone = ""
            if NewResultAddr:
                tempAddr1,tempAddr2,tempCity,tempState,tempZip = parse_address(NewResultAddr)

            # if not allData['providerAddr'] and (tempAddr1 or tempAddr2):
            #     allData['providerAddr'] = f"{tempAddr1} {tempAddr2}"
            # if not allData['providerCity'] and tempCity:
            #     allData['providerCity'] = tempCity
            # if not allData['providerState'] and tempState:
            #     allData['providerState'] = tempState
            # if not allData['providerZip'] and tempZip:
            #     allData['providerZip'] = tempZip
            
            # if not allData['providerPhone'] and NewResultPhone:
            #     allData['providerPhone'] = NewResultPhone
            focus_control(dlg)
            btnCloseSL = dlg.child_window(title="Close", control_type = "Button")
            btnCloseSL.wait("exists enabled visible ready",timeout=120,retry_interval=1)
            btnCloseSL.invoke()
            # btnCloseSL.click_input()

                
            if missing:
                # Only attempt Google if the missing set is something Google can help with
                google_fixable = {
                    "Provider address",
                    "Provider city",
                    "Provider state",
                    "Provider ZIP",
                    # "Provider phone",
                }
                needs_google = any(m in google_fixable for m in missing)
            
                if needs_google:
                    try:
                        # from GoogleSearchV2OLD import find_provider_address  # <-- filename from step 1
                        from legacy.legacy_googlesearch import find_provider_address
                    except Exception as e:
                        notify("Google Import Error", f"Cannot import google_provider_finder.find_provider_address\n\n{e}")
                        botStop = True
                        sys.exit()

                    # run google picker (user selects a result)
                    #picked = find_provider_address(PROVIDERSRCH)
            
                    # apply picked values back into allData
                    #apply_google_provider_result(allData, picked)
                    # REQUIRED by you: name the input PROVIDERSRCH

                    #PROVIDERSRCH = build_provider_search_text(allData)
            
                    # run google picker (user selects a result)
                    # -------------------------
                    # Test1: If validation missing provider details, call Google, then continue if fixed
                    # Minimal patch: if user clicks "No Accurate Result", DO NOT stop — proceed with remaining FCM code
                    # -------------------------
                    missing = get_validation_missing(allData)

                    if missing:
                        google_fixable = {
                            "Provider address",
                            "Provider city",
                            "Provider state",
                            "Provider ZIP",
                            # "Provider phone",
                        }
                        needs_google = any(m in google_fixable for m in missing)

                        if needs_google:
                            try:
                                from legacy.legacy_googlesearch import find_provider_address
                            except Exception as e:
                                notify("Google Import Error", f"Cannot import GoogleSearchV2.find_provider_address\n\n{e}")
                                botStop = True
                                sys.exit()

                            PROVIDERSRCH = build_provider_search_text(allData)

                            picked = find_provider_address(PROVIDERSRCH)
                            pick_err = (picked.get("error") or "").strip().lower()

                            # If user explicitly chooses "No Accurate Result" -> DO NOT stop, just continue.
                            if pick_err == "no_accurate_result":
                                print("[Google] User chose NO ACCURATE RESULT -> continuing without stopping.")
                            else:
                                # Apply Google result (only fills non-empty)
                                apply_google_provider_result(allData, picked)

                                # If user cancelled / blocked / exception -> stop as usual
                                if pick_err in ("cancelled", "google_blocked") or pick_err.startswith("exception"):
                                    ValidateInfo(allData)
                                    botStop = True
                                    sys.exit()

                                # Re-check after Google
                                missing_after = get_validation_missing(allData)
                                if missing_after:
                                    ValidateInfo(allData)
                                    botStop = True
                                    sys.exit()

                        else:
                            # Missing items not fixable by Google -> stop as usual
                            ValidateInfo(allData)
                            botStop = True
                            sys.exit()
                else:
                    # Missing items not fixable by Google (e.g. name/date/time rule) -> stop as usual
                    ValidateInfo(allData)
                    botStop = True
                    sys.exit()
            
            if not ValidateInfo(allData):
            # notify("Notice","For Manual Process. Missing critical information.") #migz
                botStop=True
                sys.exit()

        # pprint(allData)
        correctZipCode = allData['providerZip']
        ######
        print('Checking CMS cases and validating customer')
        process_result = run_reopen_flow(allData, app=app, notify=notify)
        if process_result['status'] != 'completed':
            botStop = True
            sys.exit()
        allData['customer'] = process_result['customer']
        print(f"Valid Employer: {allData['customer']}")
            


        ######
        focus_control(emaiDisplay)
        print(f'Navigating to Subject Line Template Builder')
        SubjectLineBuilder = emaiDisplay.child_window(auto_id="btnSubjectSearch",control_type="Button").wrapper_object()
        focus_control(SubjectLineBuilder)
        safe_click(SubjectLineBuilder)
        # dlg.wait(timeout=3)

        # dlg = Desktop(backend="uia").window(auto_id="frmEmailDispaySubjectLineBuilder",control_type="Window")
        dlg = Desktop(backend="uia").window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        dlg.wait("exists enabled visible ready",timeout=120,retry_interval=1)
        focus_control(dlg)

        # dlg.print_control_identifiers()
        tbCustomer = dlg.child_window(auto_id="tbCustomer", control_type="Edit").wrapper_object()
        tbCustomer.iface_value.SetValue("Liberty Mutual Commercial Market")

        
        # tbEmployer
        tbEmployer = dlg.child_window(auto_id="tbEmployer", control_type="Edit").wrapper_object()
        focus_control(tbEmployer)
        time.sleep(6)
        tbEmployer.iface_value.SetValue(allData['customer'])
        # # tbClaimantFirst
        tbClaimantFirst = dlg.child_window(auto_id="tbClaimantFirst", control_type="Edit").wrapper_object()
        tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        
        # # tbClaimantLast
        tbClaimantLast = dlg.child_window(auto_id="tbClaimantLast", control_type="Edit").wrapper_object()
        tbClaimantLast.iface_value.SetValue(allData['claimantLast'])
        # checkFName = tbClaimantFirst.iface_value.CurrentValue
        # checkLName = tbClaimantLast.iface_value.CurrentValue
        # if checkFName:
        #     data['claimantFirst']  = checkFNameadjus
        # if checkLName:
        #     data['claimantLast'] =  checkLName

        # pbClaimant (Pane)
        pbClaimant = dlg.child_window(auto_id="pbClaimant",control_type="Pane").wrapper_object()

        #checker
        desk = Desktop(backend="uia")
        before_handles = {w.handle for w in desk.windows(top_level_only=True,visible_only=False)}

        focus_control(pbClaimant)
        safe_click(pbClaimant)
        print(f'Searching for Claimant')
        owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        owner.wait('exists',timeout=0.5)
        ucc = owner.child_window(auto_id="frmUnityClaimClaimant",control_type="Window")
        ucc.wait('exists',timeout=3)
        focus_control(ucc)


        #Add new logic here.
        def SearchForClaimant(FName,LName,DOB,ClaimNumber):
            # tbDOB
            # tbFirst
            # tbLast
            # tbClaim
            tbDOB = ucc.child_window(auto_id="tbDOB", control_type="Edit").wrapper_object()
            tbDOB.iface_value.SetValue(DOB)

            tbFirst = ucc.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
            tbFirst.iface_value.SetValue(FName)

            tbLast = ucc.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
            tbLast.iface_value.SetValue(LName)

            tbClaim = ucc.child_window(auto_id="tbClaim", control_type="Edit").wrapper_object()
            tbClaim.iface_value.SetValue(ClaimNumber)

            SearchClaimant = ucc.child_window(auto_id="btnSearch",control_type="Button").wrapper_object()
            safe_click(SearchClaimant)

            lblStatusChecker = ucc.child_window(auto_id="lblStatus",control_type="Text")
            timeout = 300.0
            EndTime = time.monotonic() + timeout
            while time.monotonic() < EndTime:
                try:
                    lblStatus = lblStatusChecker.wrapper_object()
                    if (not lblStatus.is_visible()) or ((lblStatus.window_text() or "").strip()==""):
                        break
                except Exception:
                    break

            grid = ucc.child_window(auto_id="dgResults",control_type="Table").wrapper_object()
            AttachRow = grid.iface_grid.CurrentRowCount

            if AttachRow == 1:
                return True,"E"
            elif AttachRow > 1:
                return True,"G"
            elif AttachRow == 0:
                return False,"Z"


        def CheckClaimantResult():
            grid = ucc.child_window(auto_id="dgResults",control_type="Table")#.wrapper_object()
            AttachRow = grid.iface_grid.CurrentRowCount
            ClaimantSelected = False

            # el
            if AttachRow >= 1:
                # ---------- 1) Count EDI rows first ----------
                edi_rows = []
                for r in range(AttachRow):
                    # cell_el = grid.iface_grid.GetItem(r, 9)
                    # cell = UIAWrapper(UIAElementInfo(cell_el))
                    cell = grid.child_window(title=f"Source Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                    src = (cell.iface_value.CurrentValue or "").strip().upper()
                    if src == "EDI":
                        edi_rows.append(r)
            
                # ---------- 2) If multiple EDI -> notify, do NOT auto-pick ----------
                if len(edi_rows) > 1:
                    
                    notify("Notice", "Multiple Results! Kindly select appropriate Claimant\nClick Ok once Claim/Claimant is set")
            
                # ---------- 3) If exactly one EDI -> apply your match logic ----------
                elif len(edi_rows) == 1:
                    for r in range(AttachRow):
                        # cell_el = grid.iface_grid.GetItem(r, 6)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"DOB Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        DOB = to_mmddyyyy(cell.iface_value.CurrentValue)
            
                        # cell_el = grid.iface_grid.GetItem(r, 9)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"Source Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        Source = (cell.iface_value.CurrentValue or "").strip().upper()
            
                        # cell_el = grid.iface_grid.GetItem(r, 10)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"DOI Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        DateOfInj = to_mmddyyyy(cell.iface_value.CurrentValue)
            
                        # cell_el = grid.iface_grid.GetItem(r, 11)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"LOI Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        LineOfInsurance = (cell.iface_value.CurrentValue or "").replace(" ", "").replace("'", "").strip()
                        
                        # print(f"{allData.get('dob')} {allData.get('doi')} {(allData.get('claimType', '').replace(' ', '').lower())} {LineOfInsurance}")
                        if (Source == "EDI" and (allData.get("dob") == DOB) and (allData.get("doi") == DateOfInj) and (allData.get("claimType", "").replace(" ", "").lower() == LineOfInsurance.lower())):
                            # cell_el = grid.iface_grid.GetItem(r, 0)
                            # cell = UIAWrapper(UIAElementInfo(cell_el))
                            cell = grid.child_window(title=f"Select Row {r}", control_type="CheckBox").wrapper_object()

                            safe_click(cell)
                            ClaimantSelected = True
                            SelectClaimant = ucc.child_window(auto_id="btnSelect", control_type="Button").wrapper_object()
                            safe_click(SelectClaimant)
                            time.sleep(3)
                            return ClaimantSelected
                            break
                else:
                    SelectClaimant = ucc.child_window(auto_id="btnClose",control_type="Button").wrapper_object()
                    safe_click(SelectClaimant)
                    return ClaimantSelected

        SearchIndex = 1  
        WithPossibleSearchResult = False 
        ClaimantSelected = False
        for SearchIndex in range(1,4):
            if SearchIndex == 1:
                WithPossibleSearchResult,CountText = SearchForClaimant(None,None,allData['dob'],allData['claimNumber'])
                if WithPossibleSearchResult:
                    ClaimantSelected = CheckClaimantResult()
                    break
            elif SearchIndex == 2:
                WithPossibleSearchResult,CountText = SearchForClaimant(None,allData['claimantLast'][:3],None,allData['claimNumber'])
                if WithPossibleSearchResult:
                    ClaimantSelected = CheckClaimantResult()
                    break
            elif SearchIndex == 3:
                WithPossibleSearchResult,CountText = SearchForClaimant(allData['claimantFirst'][:3],allData['claimantLast'][:3],None,allData['claimNumber'])
                if WithPossibleSearchResult:
                    ClaimantSelected = CheckClaimantResult()
                    break

        try:
            if not ClaimantSelected or not WithPossibleSearchResult:
                SelectClaimant = ucc.child_window(auto_id="btnClose",control_type="Button").wrapper_object()
                safe_click(SelectClaimant)
        except:
            pass

        # tbClaimantFirst = dlg.child_window(auto_id="tbClaimantFirst", control_type="Edit").wrapper_object()
        # ClaimantFirstVal = (tbClaimantFirst.iface_value.CurrentValue or "").strip()
        # if ClaimantFirstVal and ClaimantSelected:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['claimantFirst'] = ClaimantFirstVal

        # tbClaimantLast = dlg.child_window(auto_id="tbClaimantLast", control_type="Edit").wrapper_object()
        # tbClaimantLastVal = (tbClaimantLast.iface_value.CurrentValue or "").strip()
        # if tbClaimantLastVal and ClaimantSelected:
        #     # tbClaimantLast.iface_value.SetValue(allData['claimantLast'])
        #     allData['claimantLast'] = tbClaimantLastVal
        #Like item Search
        focus_control(dlg)
        print(f'Navigating to Like Item Search')
        time.sleep(3)
        btnLikeItemSearch = dlg.child_window(auto_id="btnLikeItemSearch",control_type="Button").wrapper_object()
        safe_click(btnLikeItemSearch)

        #frmLikeItemsSearch
        owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        owner.wait('exists',timeout=0.5)
        lis = owner.child_window(auto_id="frmLikeItemsSearch",control_type="Window")
        lis.wait('exists',timeout=3)
        time.sleep(3)
        #--------------------ADD STOPPER!-------------------------
        def askUserContinueLikeItemSearch():
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost',True)
            answer = messagebox.askyesno("User Confirmation","For Manual Process. Kindly validate result from Like Item Search\nSelect Yes if bot would proceed. \nSelect No if bot to stop process.")
            if answer:
                return False
            else:
                return True
        #-----------------------------------------------------------

        def LikeItemSearch(SearchCriteria : str):

            tbCriteria = lis.child_window(auto_id="tbCriteria", control_type="Edit").wrapper_object()
            tbCriteria.iface_value.SetValue(SearchCriteria)

            btnSearch = lis.child_window(auto_id="btnSearch", control_type="Button").wrapper_object()
            safe_click(btnSearch)
            time.sleep(3)

            lblStatusChecker = lis.child_window(auto_id="lblNoItem",control_type="Text")
            timeout = 300.0
            EndTime = time.monotonic() + timeout
            while time.monotonic() < EndTime:
                try:
                    lblStatus = lblStatusChecker.wrapper_object()
                    if (lblStatus.is_visible()) or ((lblStatus.window_text() == "No Items Returned For Search Criteria")):
                        break
                except Exception:
                    break

            grid = lis.child_window(auto_id="dgSearch",control_type="Table").wrapper_object()
            AttachRow = grid.iface_grid.CurrentRowCount
            # for r in range(0,AttachRow):
            if AttachRow >= 1:   
                # notify("Notice","For Manual Process. Kindly validate result from Like Item Search")  
                botStop = askUserContinueLikeItemSearch()
                if botStop:
                    sys.exit() 
            else:
                return 0
                # break

            # lblNoItem = lis.child_window(auto_id="lblNoItem", control_type="Text").wrapper_object()
            # "No Items Returned For Search Criteria"
        lisCount = LikeItemSearch(allData['claimNumber']) 
        if lisCount== 0:
            lisCount = LikeItemSearch(f"{allData['claimantFirst']} {allData['claimantLast']}")

        CloseWindowIns = lis.child_window(auto_id="btnClose",control_type="Button").wrapper_object()
        safe_click(CloseWindowIns)
        time.sleep(3)
        send_keys('{SPACE}')
        time.sleep(3)

        focus_control(dlg)
        time.sleep(3)



        # drpClaimJuris = dlg.child_window(title="LOADING PLEASE WAIT", control_type="Edit").wrapper_object()
        # drpClaimJurisVal = drpClaimJuris.iface_value.CurrentValue
        # if not drpClaimJurisVal:
        #     drpClaimJuris.iface_value.SetValue(allData['claimStateFull'])
        # # tbQue
        # tbQue = dlg.child_window(auto_id="tbQue", control_type="Edit").wrapper_object()
        # tbQue.iface_value.SetValue(allData['referralNumber']) 

        # tbClaimIdentifier = dlg.child_window(auto_id="tbClaimIdentifier", control_type="Edit").wrapper_object()
        # checktbClaimIdentifier = tbClaimIdentifier.iface_value.CurrentValue
        # if not checktbClaimIdentifier:
        #     tbClaimIdentifier.iface_value.SetValue(allData['claimID'])

        # tbClaimNumber = dlg.child_window(auto_id="tbClaimNumber", control_type="Edit").wrapper_object()

        # tbClaimNumber.set_focus()
        # send_keys('{TAB}')
        # send_keys('FULL MED' ,with_spaces=True)

        # # pbRefType (Pane)
        # pbRefType = dlg.child_window(auto_id="pbRefType",control_type="Pane").wrapper_object()
        # pbRefType.click_input()

        # owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        # owner.wait('exists',timeout=0.5)
        # uft = owner.child_window(auto_id="frmUnityReferralTypes",control_type="Window")
        # uft.wait('exists',timeout=0.5)
        # uft.set_focus()
        # # uft.print_control_identifiers()
        # # cb1 = uft.child_window(control_type="Edit",found_index=0).wrapper_object()

        # # "ServiceType":URTServiceType,
        # # "refType":URTrefType,
        # # "CaseObj":URTCaseObjective
        
        # cb1 = uft.child_window(auto_id="cbServiceType",control_type="ComboBox").wrapper_object()
        # # cb1.select("Medical Full") 
        # cb1.select(allData['ServiceType'])
        # time.sleep(.5)
        # cb1 = uft.child_window(auto_id="cbReferralType",control_type="ComboBox").wrapper_object()
        # # cb1.select("Medical") 
        # cb1.select(allData['refType']) 
        # time.sleep(.5)
        # cb1 = uft.child_window(auto_id="cbUnityObjectives",control_type="ComboBox").wrapper_object()
        # # cb1.select("Coordination of Care/Services") 
        # cb1.select(allData['CaseObj']) 
        # btnOK = uft.child_window(auto_id="btnOK",control_type="Button").wrapper_object()
        # btnOK.click_input()


        dlg = Desktop(backend="uia").window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        dlg.wait("exists enabled visible ready",timeout=15,retry_interval=1)
        focus_control(dlg)

        tbClaimNumber = dlg.child_window(auto_id="tbClaimNumber", control_type="Edit").wrapper_object()
        focus_control(tbClaimNumber)
        #LOI

        # cbLOI = dlg.child_window(auto_id="cbLOI",control_type="ComboBox").wrapper_object()
        # cbLOIVal = cbLOI.iface_value.CurrentValue
        # if not cbLOIVal:
        #     # cbLOI.iface_value.SetValue(allData['claimType'])
        #     cbLOI.select(allData['claimType']) 
        # send_keys(allData['claimType'],with_spaces=True)
        send_keys('{TAB}')
        # rbClaimant
        rbClaimant = dlg.child_window(auto_id="rbClaimant",control_type="RadioButton").wrapper_object()
        rbClaimant.select()

        if ClaimantSelected == False:
            print(f'Populating Claimant Info')
            tbClaimNumber.iface_value.SetValue(allData['claimNumber'])
        # tbAddress1
            allData['addressLine1'] = titlecase(allData['addressLine1'], callback=address_callback)
            allData['addressLine2'] = titlecase(allData['addressLine2'], callback=address_callback)
            allData['city'] = titlecase(allData['city'], callback=address_callback)
            allData['state'] = titlecase(allData['state'], callback=address_callback)

            tbAddress1 = dlg.child_window(auto_id="tbAddress1", control_type="Edit").wrapper_object()
            tbAddress1.iface_value.SetValue(allData['addressLine1'])
            # tbAddress2
            tbAddress2 = dlg.child_window(auto_id="tbAddress2", control_type="Edit").wrapper_object()
            tbAddress2.iface_value.SetValue(allData['addressLine2'])
            # tbCity
            tbCity = dlg.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
            tbCity.iface_value.SetValue(allData['city'])
            # TAB enter for State
            send_keys('{TAB}')
            send_keys(allData['state'])
            # tbZip
            tbZip = dlg.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
            tbZip.iface_value.SetValue(allData['zip'])
            # tbPhone
            tbPhone = dlg.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
            tbPhone.iface_value.SetValue(allData['phoneNumber'])
        # Gender (rbMale, rbFemale, rbUnknown)
        if allData['gender'].lower() == "female":
            rbGender = dlg.child_window(auto_id="rbFemale", control_type="RadioButton").wrapper_object()
        elif allData['gender'].lower() == "male":
            rbGender = dlg.child_window(auto_id="rbMale", control_type="RadioButton").wrapper_object()
        else:
            rbGender = dlg.child_window(auto_id="rbUnknown", control_type="RadioButton").wrapper_object()
        rbGender.select()
        # tbDOB
        tbDOB = dlg.child_window(auto_id="tbDOB", control_type="Edit").wrapper_object()
        tbDOB.iface_value.SetValue(allData['dob'])

        #######################################
        #Create If Statement for Case Manager#
        if allData['ncmContactName']:
        # #cbReqNCM
            cbReqNCM = dlg.child_window(auto_id="cbReqNCM", control_type="CheckBox").wrapper_object()
            cbReqNCM.iface_toggle.Toggle()
            # tbReqNcm
            tbReqNcm = dlg.child_window(auto_id="tbReqNcm", control_type="Edit").wrapper_object()
            tbReqNcm.type_keys(allData['ncmContactName'],with_spaces=True)
            time.sleep(3)
            send_keys('{DOWN}')
            send_keys('{ENTER}')
            # rbCustomer
            rbCustomer = dlg.child_window(auto_id="rbCustomer", control_type="RadioButton").wrapper_object()
            rbCustomer.select()

        #### GAA
        if allData['city'].lower() == "texarkana" and "goodyear" in allData['customer'].lower():
            cbGAAReq = dlg.child_window(auto_id="cbGAAReq", control_type="CheckBox").wrapper_object()
            cbGAAReq.iface_toggle.Toggle()

        ########################################

        
        # cbAppointment
        print(f'Populating Appointment Details')
        cbAppointment = dlg.child_window(auto_id="cbAppointment", control_type="CheckBox").wrapper_object()

        if cbAppointment.get_toggle_state() == 0:
            if allData['nextApptDate'] and allData['nextApptTime']:
                
                cbAppointment.iface_toggle.Toggle()
                cbDateOnly = dlg.child_window(auto_id="cbDateOnly", control_type="CheckBox").wrapper_object()
                cbDateOnly.iface_toggle.Toggle()
                cbDateOnly.iface_toggle.Toggle()
                # DatePicker
                DatePicker = dlg.child_window(auto_id="DatePicker", control_type="ComboBox").wrapper_object()
                DatePicker.iface_value.SetValue(allData['nextApptDate'])
                # DatePicker.set_focus()
                DatePicker.type_keys(allData['nextApptDate'],with_spaces=True)
                # TimePicker
                TimePicker = dlg.child_window(auto_id="TimePicker", control_type="ComboBox").wrapper_object()
                # print([c.friendly_class_name() for c in TimePicker.children()])
                # print([(d.control_type(),d.window_text()) for d in TimePicker.descendants()][:20])
                
                time_str = allData['nextApptTime']
                time_24 = datetime.strptime(time_str,'%I:%M %p').strftime('%H:%M')

                # TimePicker.type_keys(time_24,with_spaces=True)
                focus_control(TimePicker)
                send_keys(time_24)
            elif allData['nextApptDate'] and not allData['nextApptTime']:
                # cbAppointment = dlg.child_window(auto_id="cbAppointment", control_type="CheckBox").wrapper_object()
                cbAppointment.iface_toggle.Toggle()
                cbDateOnly = dlg.child_window(auto_id="cbDateOnly", control_type="CheckBox").wrapper_object()
                cbDateOnly.iface_toggle.Toggle()
                # DatePicker
                DatePicker = dlg.child_window(auto_id="DatePicker", control_type="ComboBox").wrapper_object()
                DatePicker.iface_value.SetValue(allData['nextApptDate'])
                # DatePicker.set_focus()
                DatePicker.type_keys(allData['nextApptDate'],with_spaces=True)
        # rbProvider
        print(f'Navigating to Provider Search')
        rbProvider = dlg.child_window(auto_id="rbProvider", control_type="RadioButton").wrapper_object()
        rbProvider.select()
        time.sleep(3)
        # pbProvider (Pane Magnifying Glass)
        pbProvider = dlg.child_window(auto_id="pbProvider",control_type="Pane").wrapper_object()
        safe_click(pbProvider)
        time.sleep(3)
        #ADD Searching here!
        owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        owner.wait('exists',timeout=10)
        ups = owner.child_window(auto_id="frmUnityProviderLM",control_type="Window")
        ups.wait('exists ready',timeout=10)
        # ups.print_control_identifiers()
        ###-----------------------------------------------------

        # ----------------- Inputs -----------------
        #"tbFirst","tbLast","tbFacility","tbPhone","tbCity","tbZip"
        # allData['providerLast'] = "Ansari"
        tbProviderLastExtract = ups.child_window(auto_id="tbProviderLastExtract", control_type="Edit").wrapper_object()
        tbProviderLastExtractVal = (tbProviderLastExtract.iface_value.CurrentValue or "").strip()

        tbLast = ups.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
        tbLastVal = (tbLast.iface_value.CurrentValue or "").strip()
        # if tbLastVal:
        #     allData['providerLast'] = tbLastVal
        # elif tbProviderLastExtractVal:
        #     allData['providerLast'] = tbProviderLastExtractVal
        
        tbProviderFirstExtract = ups.child_window(auto_id="tbProviderFirstExtract", control_type="Edit").wrapper_object()
        tbProviderFirstExtractVal = (tbProviderFirstExtract.iface_value.CurrentValue or "").strip()
        tbFirst = ups.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
        tbFirstVal = (tbFirst.iface_value.CurrentValue or "").strip()
        # if tbFirstVal:
        #     allData['providerFirst'] = tbFirstVal
        # elif tbProviderFirstExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerFirst'] = tbProviderFirstExtractVal
        
        tbProviderNameExtract = ups.child_window(auto_id="tbProviderNameExtract", control_type="Edit").wrapper_object()
        tbProviderNameExtractVal = (tbProviderNameExtract.iface_value.CurrentValue or "").strip()
        tbFacility = ups.child_window(auto_id="tbFacility", control_type="Edit").wrapper_object()
        tbFacilityVal = (tbFacility.iface_value.CurrentValue or "").strip()
        # if tbFacilityVal:
        #     allData['providerName'] = tbFacilityVal
        # elif tbProviderNameExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerName'] = tbProviderNameExtractVal
        
        tbAddressExtract = ups.child_window(auto_id="tbAddressExtract", control_type="Edit").wrapper_object()
        tbAddressExtractVal = (tbAddressExtract.iface_value.CurrentValue or "").strip()
        # if tbAddressExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerAddr'] = tbAddressExtractVal
        
        tbPhoneExtract = ups.child_window(auto_id="tbPhoneExtract", control_type="Edit").wrapper_object()
        tbPhoneExtractVal = (tbPhoneExtract.iface_value.CurrentValue or "").strip()
        tbPhone = ups.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
        tbPhoneVal = (tbPhone.iface_value.CurrentValue or "").strip()
        # if tbPhoneVal:
        #     allData['providerPhone'] = tbPhoneVal
        # elif tbPhoneExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerPhone'] = tbPhoneExtractVal
        
        tbCityExtract = ups.child_window(auto_id="tbCityExtract", control_type="Edit").wrapper_object()
        tbCityExtractVal = (tbCityExtract.iface_value.CurrentValue or "").strip()
        tbCity = ups.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
        tbCityVal = (tbCity.iface_value.CurrentValue or "").strip()
        # if tbCityVal:
        #     allData['providerCity'] = tbCityVal
        # elif tbCityExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerCity'] = tbCityExtractVal
        
        tbStateExtract = ups.child_window(auto_id="tbStateExtract", control_type="Edit").wrapper_object()
        tbStateExtractVal = (tbStateExtract.iface_value.CurrentValue or "").strip()
        cbState = ups.child_window(auto_id="cbState", control_type="ComboBox").wrapper_object()
        cbStateVal = (cbState.iface_value.CurrentValue or "").strip()
        # if cbStateVal:
        #     allData['providerState'] = cbStateVal
        # elif tbStateExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerState'] = tbStateExtractVal
        
        tbZipExtract = ups.child_window(auto_id="tbZipExtract", control_type="Edit").wrapper_object()
        tbZipExtractVal = (tbZipExtract.iface_value.CurrentValue or "").strip()
        tbZip = ups.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
        tbZipVal = (tbZip.iface_value.CurrentValue or "").strip()
        # if tbZipVal:
        #     allData['providerZip'] = tbZipVal
        # elif tbZipExtractVal:
        #     # tbClaimantFirst.iface_value.SetValue(allData['claimantFirst'])
        #     allData['providerZip'] = tbZipExtractVal
        
        # pprint(allData)

        FacilityLName = allData['providerLast']
        FacilityFName = allData['providerFirst']
        FacilityName  = allData['providerName']
        FacPhoneNumber = allData['providerPhone']
        FacCity = allData['providerCity']
        FacState = allData['providerState']
        FacZip = allData['providerZip']

        # print("--------START Unity Provider------------------")
        # ups.print_control_identifiers()
        # print("--------END Unity Provider------------------")

        # ----------------- Helpers -----------------
        def _get_edit(auto_id):
            return ups.child_window(auto_id=auto_id, control_type="Edit").wrapper_object()

        def _set_value(ctrl, value):
            try:
                ctrl.iface_value.SetValue("")   # clear
                if value:
                    ctrl.iface_value.SetValue(value)

            except Exception:
                # Fallback to type_keys if needed
                try:
                    focus_control(ctrl)
                    ctrl.type_keys("^a{BACKSPACE}")
                    if value:
                        ctrl.type_keys(value, with_spaces=True)
                except Exception:
                    pass

        def _select_state(value):
            try:
                cb = ups.child_window(auto_id="cbState", control_type="ComboBox").wrapper_object()
                if value:
                    cb.select(value)
                else:
                    try:
                        cb.select(0)
                    except Exception:
                        pass
            except Exception:
                pass

        def _click_search():
            btn = ups.child_window(auto_id="btnSearch", control_type="Button").wrapper_object()
            safe_click(btn)
            time.sleep(3)

        def _wait_search_idle(timeout=300.0):
            lbl = ups.child_window(auto_id="lblStatus", control_type="Text")
            end_t = time.monotonic() + timeout
            while time.monotonic() < end_t:
                try:
                    w = lbl.wrapper_object()
                    if (not w.is_visible()) or ((w.window_text() or "").strip() == ""):
                        return True
                except Exception:
                    return True
                time.sleep(0.2)
            return False

        def _results_count():
            try:
                grid = ups.child_window(auto_id="dgResults", control_type="Table").wrapper_object()
                return int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)
            except Exception:
                return 0
            
        def _normalize_name(value: str) -> str:
            if not value:
                return ""
            value = value.upper().strip()
            value = re.sub(r'[^A-Z0-9\s]', ' ', value)
            value = re.sub(r'\s+', ' ', value).strip()
            return value
        
        def _facility_name_strong_match(facility_name: str, result_name: str) -> bool:
            fac = _normalize_name(facility_name)
            res = _normalize_name(result_name)
        
            if not fac or not res:
                return False
        
            # exact normalized match
            if fac == res:
                return True
        
            return False
        
        def _provider_name_strong_match(prov_first: str, prov_last: str, result_name: str) -> bool:
            first = _normalize_name(prov_first)
            last = _normalize_name(prov_last)
            res = _normalize_name(result_name)
        
            if not first or not last or not res:
                return False
        
            full1 = f"{first} {last}"
            full2 = f"{last} {first}"
            full3 = f"{last}, {first}"
        
            if res == full1 or res == full2 or res == full3:
                return True
        
            return False
        
        def _facility_name_loose_match(facility_name: str, result_name: str) -> bool:
            fac = _normalize_name(facility_name)
            res = _normalize_name(result_name)
        
            if not fac or not res:
                return False
        
            return fac in res or res in fac
        
        def _provider_name_loose_match(prov_first: str, prov_last: str, result_name: str) -> bool:
            first = _normalize_name(prov_first)
            last = _normalize_name(prov_last)
            res = _normalize_name(result_name)
        
            # if not first or not last or not res:
            #     return False
        
            return first in res and last in res
        
        def _click_select_row(grid, row_index):
            cell = grid.child_window(title=f"Select Row {row_index}", control_type="CheckBox").wrapper_object()
            safe_click(cell)

        def prvGoogleSearch(prvName):
            try:
                from legacy.legacy_googlesearch import find_provider_address
            except Exception as e:
                notify("Google Import Error", f"Cannot import GoogleSearchV2.find_provider_address\n\n{e}")
                botStop = True
                sys.exit()
            checkData = {}
            checkData["providerName"] = prvName
            checkData["providerAddr"] = allData["providerAddr"]
            checkData["providerCity"] = allData["providerCity"]
            checkData["providerState"] = allData["providerState"]
            checkData["providerZip"] = allData["providerZip"]
            checkData["providerPhone"] = allData["providerPhone"]

            PROVIDERSRCH = build_provider_search_text(checkData)
            print(PROVIDERSRCH)
            picked = find_provider_address(PROVIDERSRCH)
            pprint(picked)
            pick_err = (picked.get("error") or "").strip().lower()

            # If user explicitly chooses "No Accurate Result" -> DO NOT stop, just continue.
            if pick_err == "no_accurate_result":
                print("[Google] User chose NO ACCURATE RESULT -> continuing without stopping.")
            # else:
                # Apply Google result (only fills non-empty)
                # apply_google_provider_result(checkData, picked)

                # If user cancelled / blocked / exception -> stop as usual
                # if pick_err in ("cancelled", "google_blocked") or pick_err.startswith("exception"):
                    # ValidateInfo(allData)
                    # botStop = True
                    # sys.exit()


            return picked["providerName"]
                # Re-check after Google
                # missing_after = get_validation_missing(allData)
        
        



        def _fill_common_filters(phone, city, state, zip_):
            # Phone
            try: _set_value(_get_edit("tbPhone"), phone)
            except Exception: pass
            # City
            try: _set_value(_get_edit("tbCity"), city)
            except Exception: pass
            # State
            _select_state(state)
            # Zip
            try: _set_value(_get_edit("tbZip"), zip_)
            except Exception: pass

        def _clear_all_inputs():
            for eid in ("tbFirst","tbLast","tbFacility","tbPhone","tbCity","tbZip"):
                try:
                    _set_value(_get_edit(eid), "")
                except Exception:
                    pass
            _select_state(None)

        def _search_with(first=None, last=None, facility=None,
                        phone=None, city=None, state=None, zip_=None):
            """Populate fields, click Search, wait, return count."""
            _clear_all_inputs()
            # Names
            if first is not None:
                try: _set_value(_get_edit("tbFirst"), first)
                except Exception: pass
            if last is not None:
                try:
                    _set_value(_get_edit("tbLast"), last)
                    try:
                        _set_value(_get_edit("tbFacility"), "")
                    except Exception:
                        pass
                except Exception: pass

            # Facility
            if facility is not None:
                try: 
                    _set_value(_get_edit("tbFacility"), facility)
                    
                except Exception: pass
            # Common filters
            _fill_common_filters(phone, city, state, zip_)
            # Search
            _click_search()
            _wait_search_idle()

            return _results_count()

        def _close_dialog_if_needed():
            try:
                btn = ups.child_window(auto_id="btnClose", control_type="Button").wrapper_object()
                safe_click(btn)
            except Exception:
                pass

        # ----------------- Main search logic -----------------
        
        # ----------------- Execute -----------------
        rows_found = 0
        SelectedPrvResult = False
        rows_found,SelectedPrvResult = run_provider_search()
        # print(f"Rows found: {rows_found}")
        if not isManualEntered:
            print(f'Adding new provider information')
            # if rows_found == 0:
            btnAddNew= ups.child_window(auto_id="btnAddNew",control_type="Button").wrapper_object()
            safe_click(btnAddNew)
            time.sleep(2)
            upan = ups.child_window(auto_id="frmUnityProviderAddNew",control_type="Window")
            upan.wait('exists',timeout=5)
            # upan.print_control_identifiers()
            time.sleep(2)
            if allData['providerName'] and (not allData['providerLast'].strip() or not allData['providerFirst'].strip()):
                tbFacilityName = upan.child_window(auto_id="tbFacilityName", control_type="Edit").wrapper_object()
                tbFacilityName.iface_value.SetValue(allData['providerName'])
            ProfName = f"{allData['providerFirst']} {allData['providerLast']}"
            if ProfName: #ProfName.strip() != allData['providerName'].strip()
                tbName = upan.child_window(auto_id="tbName", control_type="Edit").wrapper_object()
                tbName.iface_value.SetValue(ProfName)
                
            tbAddress1= upan.child_window(auto_id="tbAddress1", control_type="Edit").wrapper_object()
            tbAddress1.iface_value.SetValue(allData['providerAddr'])
            # tbAddress2= upan.child_window(auto_id="tbName", control_type="Edit").wrapper_object()
            # tbName.iface_value.SetValue(allData['providerName'])
            tbCity= upan.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
            tbCity.iface_value.SetValue(allData['providerCity'])
            cbState = upan.child_window(auto_id="cbState",control_type="ComboBox").wrapper_object()
            cbState.select(allData['providerState']) 
            tbZip= upan.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
            tbZip.iface_value.SetValue(allData['providerZip'])
            tbPhone= upan.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
            tbPhone.iface_value.SetValue(allData['providerPhone'])

            notify("Notice","Please validate if provider information is correct. User to Manual Click on Add Provider.")
                # btnAddPrv = dlg.child_window(auto_id="btnAdd",control_type="Button").wrapper_object()
                # btnAddPrv.click_input()
                

            # else:
            #     btnSelect = ups.child_window(auto_id="btnSelect",control_type="Button").wrapper_object()
            #     btnSelect.click_input()
            #     _close_dialog_if_needed()
        ###------------------------------------------------------------------


        # tbDOIdt
        tbDOIdt = dlg.child_window(auto_id="tbDOIdt", control_type="Edit").wrapper_object()
        tbDOIdtVal = tbDOIdt.iface_value.CurrentValue
        if not tbDOIdtVal:
            tbDOIdt.iface_value.SetValue(allData['doi'])

        # tbSSN
        # tbSSN = dlg.child_window(auto_id="tbSSN", control_type="Edit").wrapper_object()
        # tbSSN.iface_value.SetValue(allData['claimantSSN'])
        # tbReferralSource
        tbReferralSource = dlg.child_window(auto_id="tbReferralSource", control_type="Edit").wrapper_object()
        tbReferralSource.iface_value.SetValue(allData['refSource'])
        # tbAdjuster
        print(f'Navigating to Adjust Search')
        AdjusterName = allData['adjuster']
        tbAdjuster = dlg.child_window(auto_id="tbAdjuster", control_type="Edit").wrapper_object()
        tbAdjuster.iface_value.SetValue(AdjusterName)
        # pbAdjusterSearch (Pane)
        pbAdjusterSearch = dlg.child_window(auto_id="pbAdjusterSearch",control_type="Pane").wrapper_object()
        safe_click(pbAdjusterSearch)
        
        owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        owner.wait('exists',timeout=5)
        uas = owner.child_window(auto_id="frmUnityAdjusterSearch",control_type="Window")
        uas.wait('exists',timeout=5)

        parts = AdjusterName.strip().split()
        # Initialize defaults
        AdjusterFirstName = ""
        AdjusterLastName = ""
        if len(parts) == 1:
            AdjusterFirstName = parts[0]
        elif len(parts) == 2:
            AdjusterFirstName, AdjusterLastName = parts
        else:
            # For names with middle name or initial
            AdjusterFirstName = parts[0]
            AdjusterLastName = parts[-1]

        SearchAdjuster = uas.child_window(auto_id="btnSearch",control_type="Button").wrapper_object()
        safe_click(SearchAdjuster)

        # lblStatus.Name ="Searching please wait"
        lblStatusChecker = uas.child_window(auto_id="lblProgress",control_type="Text")
        timeout = 300.0
        EndTime = time.monotonic() + timeout
        while time.monotonic() < EndTime:
            try:
                lblStatus = lblStatusChecker.wrapper_object()
                if (not lblStatus.is_visible()) or ((lblStatus.window_text() or "").strip()==""):
                    break
            except Exception:
                break


        grid = uas.child_window(auto_id="dgAdjusters",control_type="Table")#.wrapper_object()
        AttachRow = grid.iface_grid.CurrentRowCount

        # el
        AdjusterFName = ""
        AdjusterLName= ""
        if AttachRow >= 1:
            validateAdjuster = False
            for r in range(AttachRow):
                print(f'Validating Adjuster information. {r} of {AttachRow}')
                # cell_el = grid.iface_grid.GetItem(r,3)
                # cell = UIAWrapper(UIAElementInfo(cell_el))
                # adjusterPhone = cell.iface_value.CurrentValue

                # cell_el = grid.iface_grid.GetItem(r,5)
                # cell = UIAWrapper(UIAElementInfo(cell_el))
                cell = grid.child_window(title=f"Physical Address Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                adjPhyAddr = cell.iface_value.CurrentValue
                adjAddrFull = f"{allData['adjAddrFull']}"
                adjAddrMail = f"{allData['adjAddrMail']}"

                TempAddress = expand_suffix_long(adjPhyAddr)
                RealAddress = expand_suffix_long(adjAddrFull)
                ComparisonResult = addressMatch(TempAddress,RealAddress)

                TempAddress1 = expand_suffix_long(adjPhyAddr)
                RealAddress1 = expand_suffix_long(adjAddrMail)
                ComparisonResult1 = addressMatch(TempAddress1, RealAddress1)
                
                if ComparisonResult or ComparisonResult1:
                    # cell_el = grid.iface_grid.GetItem(r,0)
                    # cell = UIAWrapper(UIAElementInfo(cell_el))
                    
                    cell = grid.child_window(title=f"Select Row {r}", control_type="CheckBox").wrapper_object()
                    safe_click(cell)
                    time.sleep(2)
                    SelectAdjuster = uas.child_window(auto_id="btnSetAdjuster",control_type="Button").wrapper_object()
                    safe_click(SelectAdjuster)

                    validateAdjuster = True
                    break
            # if not validateAdjuster:
            #     notify("Notice",f"Multiple Results. Please select correct Adjuster Information from the Results.\nAdjuster Full Address:{allData['adjAddrFull']}\nClick Ok once Adjuster is selected and set.")

        elif AttachRow == 0:
            print(f'Add New Adjuster Info')
            btnAddNew = uas.child_window(auto_id="btnAddNew",control_type="Button").wrapper_object()
            safe_click(btnAddNew)

            newowner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
            newowner.wait('exists',timeout=5.0)
            uaan = newowner.child_window(auto_id="frmUnityAdjusterAddNew",control_type="Window")
            uaan.wait('exists',timeout=5.0)

            RawAdjusterName = allData['adjuster'].strip()

            if "," in RawAdjusterName:
                AdjusterLName,restName = [name.strip() for name in RawAdjusterName.split(",", 1)]
                AdjusterFName = restName.split()[0]
            else:
                adjusterNameSplit = RawAdjusterName.split()
                AdjusterFName = adjusterNameSplit[0] if adjusterNameSplit else ""
                AdjusterLName = adjusterNameSplit[-1] if len(adjusterNameSplit)>1 else ""
            
            
            tbFirst = uaan.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
            tbFirst.iface_value.SetValue(AdjusterFName)

            tbLast = uaan.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
            tbLast.iface_value.SetValue(AdjusterLName)

            tbEmail = uaan.child_window(auto_id="tbEmail", control_type="Edit").wrapper_object()
            tbEmail.iface_value.SetValue(allData['adjEmail'])

            tbPhone = uaan.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
            tbPhone.iface_value.SetValue(allData['adjPhone'])

            # tbFax = uaan.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
            # tbFax.iface_value.SetValue(AdjusterFName)

            tbAddress = uaan.child_window(auto_id="tbAddress", control_type="Edit").wrapper_object()
            tbAddress.iface_value.SetValue(allData['adjAddr1'])

            tbAddress2 = uaan.child_window(auto_id="tbAddress2", control_type="Edit").wrapper_object()
            tbAddress2.iface_value.SetValue(allData['adjAddr2'])

            tbCity = uaan.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
            tbCity.iface_value.SetValue(allData['adjCity'])

            cbState = uaan.child_window(auto_id="cbState",control_type="ComboBox").wrapper_object()
            cbState.select(allData['adjState']) 

            tbZip = uaan.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
            tbZip.iface_value.SetValue(allData['adjZip'])

            notify("Notice","Please validate the Adjuster Information and Manually Click Add the Adjuster then Click Ok.")
            # btnAddAdjuster = uaan.child_window(auto_id="btnAddAdjuster",control_type="Button").wrapper_object()
            # btnAddAdjuster.click_input()
            # CloseWindowAdjuster = uas.child_window(auto_id="btnClose",control_type="Button").wrapper_object()
            # CloseWindowAdjuster.click_input()

        if not validateAdjuster:
            print(f'Add New Adjuster Info')
            btnAddNew = uas.child_window(auto_id="btnAddNew",control_type="Button").wrapper_object()
            safe_click(btnAddNew)

            newowner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
            newowner.wait('exists',timeout=5.0)
            uaan = newowner.child_window(auto_id="frmUnityAdjusterAddNew",control_type="Window")
            uaan.wait('exists',timeout=5.0)

            RawAdjusterName = allData['adjuster'].strip()

            if "," in RawAdjusterName:
                AdjusterLName,restName = [name.strip() for name in RawAdjusterName.split(",", 1)]
                AdjusterFName = restName.split()[0]
            else:
                adjusterNameSplit = RawAdjusterName.split()
                AdjusterFName = adjusterNameSplit[0] if adjusterNameSplit else ""
                AdjusterLName = adjusterNameSplit[-1] if len(adjusterNameSplit)>1 else ""
            
            
            tbFirst = uaan.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
            tbFirst.iface_value.SetValue(AdjusterFName)

            tbLast = uaan.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
            tbLast.iface_value.SetValue(AdjusterLName)

            tbEmail = uaan.child_window(auto_id="tbEmail", control_type="Edit").wrapper_object()
            tbEmail.iface_value.SetValue(allData['adjEmail'])

            tbPhone = uaan.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
            tbPhone.iface_value.SetValue(allData['adjPhone'])

            # tbFax = uaan.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
            # tbFax.iface_value.SetValue(AdjusterFName)

            tbAddress = uaan.child_window(auto_id="tbAddress", control_type="Edit").wrapper_object()
            tbAddress.iface_value.SetValue(allData['adjAddr1'])

            tbAddress2 = uaan.child_window(auto_id="tbAddress2", control_type="Edit").wrapper_object()
            tbAddress2.iface_value.SetValue(allData['adjAddr2'])

            tbCity = uaan.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
            tbCity.iface_value.SetValue(allData['adjCity'])

            cbState = uaan.child_window(auto_id="cbState",control_type="ComboBox").wrapper_object()
            cbState.select(allData['adjState']) 

            tbZip = uaan.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
            tbZip.iface_value.SetValue(allData['adjZip'])

            # notify("Notice","Please validate the Adjuster Information and Manually Add the Adjuster.")
            notify("Notice","Please validate the Adjuster Information and Manually Click Add the Adjuster then Click Ok.")

        # tbClaimantAttorney
        # pbClaimantAttorney (Pane)
        
        time.sleep(2)
        ClaimAtty = allData['claimantAttyName']
        ClaimantPhone = allData['claimantAttyPhone']
        ClaimantState = allData['claimantAttyState']
        ClaimantZip = allData['claimantAttyZip']
        ClaimantCity = allData['claimantAttyCity']

        if " " in ClaimantPhone:
            ClaimantPhoneParts = ClaimantPhone.split()
            if len(ClaimantPhoneParts) > 1:
                ClaimantPhone = ClaimantPhoneParts[0]

        if ClaimAtty:
            print(f'Navigating to Attorney Search')
            
            try:
                pbClaimantAttorney = dlg.child_window(auto_id="pbClaimantAttorney",control_type="Pane").wrapper_object()
                safe_click(pbClaimantAttorney)
            except:   
                pbClaimantAttorney = dlg.child_window(auto_id="pbClaimantAttorneyCheckmark",control_type="Pane").wrapper_object()
                safe_click(pbClaimantAttorney)

            owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
            owner.wait('exists',timeout=5)
            uads = owner.child_window(auto_id="frmUnityAttorneySearch",control_type="Window")
            uads.wait('exists',timeout=5)


            #frmUnityAttorneySearch
            parts = ClaimAtty.strip().split()
            # Initialize defaults
            ClaimAttyFirstName = ""
            ClaimAttyLastName = ""
            if len(parts) == 1:
                ClaimAttyFirstName = parts[0]
            elif len(parts) == 2:
                ClaimAttyFirstName, ClaimAttyLastName = parts
            else:
                # For names with middle name or initial
                ClaimAttyFirstName = parts[0]
                ClaimAttyLastName = parts[-1]

            # ClaimAttyFirstName = "Andrew"
            # ClaimAttyLastName = "Creech"    
            # print("First Name:", ClaimAttyFirstName)
            # print("Last Name:", ClaimAttyLastName)

            def _get_edit_Atty(auto_id):
                return uads.child_window(auto_id=auto_id, control_type="Edit").wrapper_object()
            
            def _select_stateAtty(value):
                try:
                    cb = uads.child_window(auto_id="cbState", control_type="ComboBox").wrapper_object()
                    if value:
                        cb.select(value)
                    else:
                        try:
                            cb.select(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _fill_common_filters_Atty(phone, city, state, zip_):
            # Phone
                try: _set_value(_get_edit_Atty("tbPhone"), phone)
                except Exception: pass
                # City
                try: _set_value(_get_edit_Atty("tbCity"), city)
                except Exception: pass
                # Zip
                try: _set_value(_get_edit_Atty("tbZip"), zip_)
                except Exception: pass
                # State
                try:
                    _select_stateAtty(state)
                except Exception: pass
                
            
            def _wait_search_idle_atty(timeout=300.0):
                lbl = uads.child_window(auto_id="lblStatus", control_type="Text")
                end_t = time.monotonic() + timeout
                while time.monotonic() < end_t:
                    try:
                        w = lbl.wrapper_object()
                        if (not w.is_visible()) or ((w.window_text() or "").strip() == ""):
                            return True
                    except Exception:
                        return True
                    time.sleep(0.2)
                return False
            
            def _select_state_atty(value):
                try:
                    cb = uads.child_window(auto_id="cbState", control_type="ComboBox").wrapper_object()
                    if value:
                        cb.select(value)
                    else:
                        try:
                            cb.select(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _results_count_atty():
                try:
                    grid = uads.child_window(auto_id="dgResults", control_type="Table").wrapper_object()
                    return int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)
                except Exception:
                    return 0
            def _clear_all_inputs_atty():
                for eid in ("tbFirst","tbLast","tbFirmName","tbPhone","tbCity","tbZip"):
                    try:
                        _set_value(_get_edit_Atty(eid), "")
                    except Exception:
                        pass
                _select_state_atty(None)
            
            
            def _search_with_atty(first=None, last=None, FirmName=None,
                        phone=None, city=None, state=None, zip_=None):
                """Populate fields, click Search, wait, return count."""
                _clear_all_inputs_atty()
                # Names
                if first is not None:
                    try: _set_value(_get_edit_Atty("tbFirst"), first)
                    except Exception: pass
                if last is not None:
                    try: _set_value(_get_edit_Atty("tbLast"), last)
                    except Exception: pass

                # FirmName
                if FirmName is not None:
                    try: _set_value(_get_edit_Atty("tbFirmName"), FirmName)
                    except Exception: pass
                # Common filters
                _fill_common_filters_Atty(phone, city, state, zip_)
                time.sleep(3)
                # Search
                btn = uads.child_window(auto_id="btnSearch", control_type="Button").wrapper_object()
                safe_click(btn)
                # _click_search()
                _wait_search_idle_atty()

                return _results_count_atty()
            

            ##########ATTY TEST
            def _norm(s) -> str:
                return " ".join((s or "").replace("\n", " ").strip().split()).lower()

            def _in_match(needle: str, hay: str) -> bool:
                needle_n = _norm(needle)
                if not needle_n:
                    return True
                return needle_n in _norm(hay)

            def _addr_match(addr_expected: str, addr_row: str) -> bool:
                if not _norm(addr_expected):
                    return True
                return bool(addressMatch(addr_expected, addr_row))

            def _base_phone(phone: str) -> str:
                parts = (phone or "").strip().split()
                return parts[0] if parts else ""

            def _phone_match(expected_phone: str, row_phone: str) -> bool:
                if not (expected_phone or "").strip():
                    return True

                expected_base = _base_phone(expected_phone)

                try:
                    realPhone = (format_phone_us(expected_base) or "").strip()
                except Exception:
                    realPhone = expected_base.strip()

                try:
                    tempPhone = (format_phone_us(row_phone) or "").strip()
                except Exception:
                    tempPhone = (row_phone or "").strip()

                # fallback if formatter returns empty
                if not realPhone or not tempPhone:
                    digits_real = re.sub(r"\D+", "", expected_base)
                    digits_temp = re.sub(r"\D+", "", row_phone or "")
                    return (not digits_real) or (digits_real in digits_temp)

                return realPhone == tempPhone

            def select_matching_attorney_row_using_your_format() -> bool:
                ClaimAtty = allData['claimantAttyName']
                ClaimantAttyPhone = allData['claimantAttyPhone']
                ClaimantAttyState = allData['claimantAttyState']
                ClaimantAttyZip = allData['claimantAttyZip']
                ClaimantAttyCity = allData['claimantAttyCity']
                # ClaimAttyFirstName = "Andrew"
                # ClaimAttyLastName = "Creech"
                claimantAttyFirm = ""
                ClaimantAttyAddr1 = allData['claimantAttyAddr1']
                ClaimantAttyAddr2 = allData['claimantAttyAddr2']

                if " " in ClaimantAttyPhone:
                    ClaimantPhoneParts = ClaimantAttyPhone.split()
                    if len(ClaimantPhoneParts) > 1:
                        ClaimantAttyPhone = ClaimantPhoneParts[0]
                try:
                    grid = uads.child_window(auto_id="dgResults", control_type="Table")#.wrapper_object()
                    rows = int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)
                    if rows <= 0:
                        return False

                    # Start at 1 if row 0 is header; if not, change to 0
                    start_row = 0

                    for r in range(start_row, rows):
                        print(f'Validating Result. {r} out of {rows}')
                        rule_A =False
                        rule_B =False
                        rule_C=False
                        # --- READ VALUES USING YOUR FORMAT ---
                        # col 2 First Name
                        # cell_el = grid.iface_grid.GetItem(r, 2)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"First Name Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        rAttyFName = (cell.iface_value.CurrentValue or "").strip()

                        # col 3 Last Name
                        # cell_el = grid.iface_grid.GetItem(r, 3)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"Last Name Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        rAttyLName = (cell.iface_value.CurrentValue or "").strip()

                        # col 4 Firm Name
                        # cell_el = grid.iface_grid.GetItem(r, 4)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"Firm Name Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        rFirmName = (cell.iface_value.CurrentValue or "").strip()

                        # col 5 Address (single string)
                        # cell_el = grid.iface_grid.GetItem(r, 5)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"Address Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        rAttyAddr = (cell.iface_value.CurrentValue or "").strip()

                        # col 6 Phone
                        # cell_el = grid.iface_grid.GetItem(r, 6)
                        # cell = UIAWrapper(UIAElementInfo(cell_el))
                        cell = grid.child_window(title=f"Phone Row {r}, Not sorted.", control_type="Edit").wrapper_object()
                        rAttyPhone = (cell.iface_value.CurrentValue or "").strip()

                        # --- OPTIONAL EXTRA FILTERS (only if you provided them) ---
                        # If you pass these, we require them regardless of rule A/B/C.
                        if claimantAttyFirm and not _in_match(claimantAttyFirm, rFirmName):
                            continue
                        if ClaimantAttyCity and not _in_match(ClaimantAttyCity, rAttyAddr):
                            continue
                        if ClaimantAttyState and not _in_match(ClaimantAttyState, rAttyAddr):
                            continue
                        if ClaimantAttyZip and not _in_match(ClaimantAttyZip, rAttyAddr):
                            continue

                        # --- BASE NAME MATCH FLAGS ---
                        f_ok = _in_match(ClaimAttyFirstName, rAttyFName) if (ClaimAttyFirstName or "").strip() else False
                        l_ok = _in_match(ClaimAttyLastName, rAttyLName) if (ClaimAttyLastName or "").strip() else False

                        # A) First OR Last
                        

                        # For B/C you said: "first name and last name and ..."
                        have_both_names = bool((ClaimAttyFirstName or "").strip()) and bool((ClaimAttyLastName or "").strip())
                        names_both_ok = have_both_names and _in_match(ClaimAttyFirstName, rAttyFName) and _in_match(ClaimAttyLastName, rAttyLName)

                        # B) First + Last + Address (Addr1/Addr2; match either)
                        have_any_addr = bool(_norm(ClaimantAttyAddr1) or _norm(ClaimantAttyAddr2))
                        addr_ok = True
                        if have_any_addr:
                            addr_ok = (
                                _addr_match(ClaimantAttyAddr1, rAttyAddr) or
                                _addr_match(ClaimantAttyAddr2, rAttyAddr)
                            )
                        rule_B = names_both_ok and have_any_addr and addr_ok

                        # C) First + Last + Phone
                        have_phone = bool((ClaimantAttyPhone or "").strip())
                        phone_ok = _phone_match(ClaimantAttyPhone, rAttyPhone) if have_phone else False
                        rule_C = names_both_ok and have_phone and phone_ok

                        # ---- SELECT IF ANY RULE HIT ----
                        if f_ok and l_ok:
                            if not (rule_B or rule_C):
                                continue
                        else:
                            # if f_ok or l_ok:
                            if not ClaimAttyFirstName or not ClaimAttyLastName:
                                rule_A = f_ok or l_ok
                                if not (rule_A):
                                    continue

                        # Click checkbox column 0
                        # print(f'testing  {rAttyFName} {rAttyLName} {rAttyAddr}')
                        # print(f'test {rule_A} {rule_B} {rule_C}')
                        if rule_A or rule_B or rule_C:
                            try:
                                print(f'Selecting {rAttyFName} {rAttyLName} {rAttyAddr}')
                                # select_el = grid.iface_grid.GetItem(r, 0)
                                # select_cell = UIAWrapper(UIAElementInfo(select_el))
                                select_cell = grid.child_window(title=f"Select Row {r}", control_type="CheckBox").wrapper_object()
                                safe_click(select_cell)
                                time.sleep(2)
                                SelectAtty = uads.child_window(auto_id="btnSelect",control_type="Button").wrapper_object()
                                safe_click(SelectAtty)
                                return True
                            except Exception:
                                try:
                                    # select_el = grid.iface_grid.GetItem(r, 0)
                                    # select_cell = UIAWrapper(UIAElementInfo(select_el))
                                    select_cell = grid.child_window(title=f"Select Row {r}", control_type="CheckBox").wrapper_object()
                                    kids = select_cell.children()
                                    if kids:
                                        safe_click(kids[0])
                                        return True
                                except Exception:
                                    pass
                    return False

                except Exception:
                    return False






            #############
            def _click_first_row_if_any_atty():
                global isManualEnteredAtty
                try:
                    grid = uads.child_window(auto_id="dgResults", control_type="Table").wrapper_object()
                    rows = int(getattr(grid.iface_grid, "CurrentRowCount", 0) or 0)

                    for r in range(rows):
                        if rows >= 1:
                            cell_el = grid.iface_grid.GetItem(r,2)
                            cell = UIAWrapper(UIAElementInfo(cell_el))
                            rAttyFName = cell.iface_value.CurrentValue

                            cell_el = grid.iface_grid.GetItem(r,3)
                            cell = UIAWrapper(UIAElementInfo(cell_el))
                            rAttyLName = cell.iface_value.CurrentValue

                            cell_el = grid.iface_grid.GetItem(r,4)
                            cell = UIAWrapper(UIAElementInfo(cell_el))
                            rFirmName = cell.iface_value.CurrentValue

                            cell_el = grid.iface_grid.GetItem(r,5)
                            cell = UIAWrapper(UIAElementInfo(cell_el))
                            rAttyAddr = cell.iface_value.CurrentValue

                            cell_el = grid.iface_grid.GetItem(r,6)
                            cell = UIAWrapper(UIAElementInfo(cell_el))
                            rAttyPhone = cell.iface_value.CurrentValue

                            print(f"{rAttyFName}\n{rAttyLName}\n{rFirmName}\n{rAttyAddr}\n{rAttyPhone}")

                            atyAddrFull = f"{allData['claimantAttyAddr1']} {allData['claimantAttyAddr2']} {allData['claimantAttyCity']} {allData['claimantAttyState']} {allData['claimantAttyZip']}"

                            TempAddress = expand_suffix_long(rAttyAddr)
                            RealAddress = expand_suffix_long(atyAddrFull)
                            ComparisonResult = addressMatch(TempAddress,RealAddress)

                            if ClaimAttyFirstName and ClaimAttyFirstName in rAttyFName:
                                checkAttyFName = True
                            if ClaimAttyLastName and ClaimAttyLastName in rAttyLName:
                                checkAttyLName = True
                            

                            if ComparisonResult:
                                cell_el = grid.iface_grid.GetItem(r,0)
                                cell = UIAWrapper(UIAElementInfo(cell_el))
                                safe_click(cell)
                                time.sleep(2)
                                SelectAtty = uads.child_window(auto_id="btnSelect",control_type="Button").wrapper_object()
                                safe_click(SelectAtty)
                                validateAdjuster = True
                            # notify("Notice",f"Please Select the correct information from the Attorney Results. \n\nAttorney Name: {allData['claimantAttyName']} \nProvider Address: {allData['claimantAttyAddr1']} {allData['claimantAttyAddr2']} {allData['claimantAttyCity']} {allData['claimantAttyState']} {allData['claimantAttyZip']}\nProvider Phone: {allData['claimantAttyPhone']}")
                            isManualEnteredAtty = True
                            return True
                except Exception:
                    pass
                return False
                
                # ClaimAtty = allData['claimantAttyName']
                # ClaimantPhone = allData['claimantAttyPhone']
                # ClaimantState = allData['claimantAttyState']
                # allData['claimantAttyAddr1']
                # ClaimantZip = allData['claimantAttyZip']

            def run_atty_search():
                firstAttempAtty = False
                global isManualEntered 
                isManualEntered = False
                if ClaimantPhone:
                    count = _search_with_atty(first=None, last=None, FirmName=None,
                                        phone=ClaimantPhone, city=None, state=None, zip_=None)
                    if count <= 10:
                        firstAttempAtty = select_matching_attorney_row_using_your_format()
                        if firstAttempAtty:
                            isManualEntered= firstAttempAtty
                            return count
                if not firstAttempAtty:    
                    if ClaimAttyLastName or ClaimAttyFirstName or (ClaimantZip and ClaimantState and ClaimantCity) :
                        count = _search_with_atty(first=ClaimAttyFirstName[:3], last=ClaimAttyLastName, FirmName=None,
                                            phone=None, city=ClaimantCity, state=ClaimantState, zip_=ClaimantZip)
                        if count > 0:
                            
                            isManualEntered= select_matching_attorney_row_using_your_format()
                            return count
                    isManualEntered = False    
                    return 0
                
            attyCount = run_atty_search()
            # print(f"Atty search: {isManualEntered}")
            if not isManualEntered:
                print(f'Adding new attorney info')
                if attyCount == 0:
                    btnAddNew= uads.child_window(auto_id="btnAddNew",control_type="Button").wrapper_object()
                    safe_click(btnAddNew)

                    uatan = uads.child_window(auto_id="frmUnityAttorneyAddNew",control_type="Window")
                    uatan.wait('exists',timeout=3)
                    tbFirst = uatan.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
                    tbFirst.iface_value.SetValue(ClaimAttyFirstName)
                    tbLast = uatan.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
                    tbLast.iface_value.SetValue(ClaimAttyLastName)
                    tbAddress1= uatan.child_window(auto_id="tbAddress1", control_type="Edit").wrapper_object()
                    tbAddress1.iface_value.SetValue(allData['claimantAttyAddr1'])
                    tbAddress2= uatan.child_window(auto_id="tbAddress2", control_type="Edit").wrapper_object()
                    tbAddress2.iface_value.SetValue(allData['claimantAttyAddr2'])
                    tbCity= uatan.child_window(auto_id="tbCity", control_type="Edit").wrapper_object()
                    tbCity.iface_value.SetValue(allData['claimantAttyCity'])
                    cbState = uatan.child_window(auto_id="cbState",control_type="ComboBox").wrapper_object()
                    cbState.select(allData['claimantAttyState']) 
                    tbZip= uatan.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
                    tbZip.iface_value.SetValue(allData['claimantAttyZip'])
                    tbPhone= uatan.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
                    tbPhone.iface_value.SetValue(ClaimantPhone) # migz

                    notify("Notice","Please validate if Attorney information is correct. User to Manual Click on Add Attorney.")


            # tbFirst = uads.child_window(auto_id="tbFirst", control_type="Edit").wrapper_object()
            # tbFirst.iface_value.SetValue(ClaimAttyFirstName[:3])
            # tbLast = uads.child_window(auto_id="tbLast", control_type="Edit").wrapper_object()
            # tbLast.iface_value.SetValue(ClaimAttyLastName)
            # tbPhone = uads.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
            # tbPhone.iface_value.SetValue(ClaimantPhone)
            # cbState = uads.child_window(auto_id="cbState",control_type="ComboBox").wrapper_object()
            # cbState.select(ClaimantState) 
            # tbZip = uads.child_window(auto_id="tbZip", control_type="Edit").wrapper_object()
            # tbZip.iface_value.SetValue(ClaimantZip)

            # SearchAdjuster = uads.child_window(auto_id="btnSearch",control_type="Button").wrapper_object()
            # SearchAdjuster.click_input()

            # lblStatus.Name ="Searching please wait"
            # lblStatusChecker = uads.child_window(auto_id="lblProgress",control_type="Text")
            # timeout = 300.0
            # EndTime = time.monotonic() + timeout
            # while time.monotonic() < EndTime:
            #     try:
            #         lblStatus = lblStatusChecker.wrapper_object()
            #         if (not lblStatus.is_visible()) or ((lblStatus.window_text() or "").strip()==""):
            #             break
            #     except Exception:
            #         break


            # grid = uads.child_window(auto_id="dgResults",control_type="Table").wrapper_object()
            # AttachRow = grid.iface_grid.CurrentRowCount

            # for r in range(0,AttachRow):   
            #     cell_el = grid.iface_grid.GetItem(r,0)
            #     cell = UIAWrapper(UIAElementInfo(cell_el))
            #     cell.click_input()

            #     SelectAtty = uads.child_window(auto_id="btnSelect",control_type="Button").wrapper_object()
            #     SelectAtty.click_input()
            #     break

            # if AttachRow == 0:
            #     CloseWindowAtty = uads.child_window(auto_id="btnClose",control_type="Button").wrapper_object()
            #     CloseWindowAtty.click_input()

        # pbDefeneseAttorney(Pane)
        defAtty= ""
        if defAtty:
            pbDefeneseAttorney = dlg.child_window(auto_id="pbDefeneseAttorney",control_type="Pane").wrapper_object()
            safe_click(pbDefeneseAttorney)
            time.sleep(5)
            owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
            owner.wait('exists',timeout=0.5)
            uads = owner.child_window(auto_id="frmUnityAttorneySearch",control_type="Window")
            uads.wait('exists',timeout=0.5)


            CloseWindowAdjuster = uads.child_window(auto_id="btnClose",control_type="Button").wrapper_object()
            safe_click(CloseWindowAdjuster)
        #frmUnityAttorneySearch
        #btnClose

        #Unity Body Part Name:"Provider Info"
        cbBodyPart = dlg.child_window(title="Provider Info", control_type="Edit").wrapper_object()
        cbBodyPartVal = cbBodyPart.iface_value.CurrentValue
        if not cbBodyPartVal:
            cbBodyPart.iface_value.SetValue(allData['bodyPart']) 

        # TAB Injury Type
        cbInjuryType = dlg.child_window(auto_id="cbInjuryType", control_type="ComboBox").wrapper_object()
        cbInjTypeVal = cbInjuryType.iface_value.CurrentValue
        

        # cbInjuryType.iface_value.SetValue(allData['injuryType'])
        # send_keys('{TAB}')
        # send_keys(allData['injuryType'],with_spaces=True) #All Other Specific Injuries, NOC
        # cbInjuryType cbInjuryCause

        # TAB Injury Cause
        cbInjuryCause = dlg.child_window(auto_id="cbInjuryCause", control_type="ComboBox").wrapper_object()
        cbInjCauseVal = cbInjuryCause.iface_value.CurrentValue

        if not cbInjTypeVal or not cbInjCauseVal:
            notify("Notice",f"Injury Type: {allData['injuryType']}\nInjury Cause: {allData['injuryCause']}")
        # cbInjuryCause.iface_value.SetValue(allData['injuryCause'])
        # send_keys('{TAB}')
        # send_keys(allData['injuryCause'],with_spaces=True) #'Other - Miscellaneous, NOC
        

        # btnSpecialInstrucitons
        # SpecialInstBtn = dlg.child_window(auto_id="btnSpecialInstrucitons",control_type="Button").wrapper_object()
        # SpecialInstBtn.click_input()
        # time.sleep(3)

        # owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        # owner.wait('exists',timeout=0.5)
        # specIns = owner.child_window(auto_id="frmSpecialInstructions",control_type="Window")
        # specIns.wait('exists',timeout=0.5)
        # time.sleep(3)
        # rtcInstruction = specIns.child_window(auto_id="rtbSpecialInstructions", control_type="Document").wrapper_object()
        # SpecialInstructionText = allData['specialInstructions']
        # rtcInstruction.iface_value.SetValue(SpecialInstructionText)
        # CloseWindowIns = specIns.child_window(auto_id="btnOk",control_type="Button").wrapper_object()
        # CloseWindowIns.click_input()

        cbClaimType = dlg.child_window(auto_id="cbClaimType", control_type="ComboBox").wrapper_object()
        if CTMedOnly:
            cbClaimType.iface_value.SetValue("Medical Only")
        else:
            cbClaimType.iface_value.SetValue("Lost Time")
        # cbClaimType.select("Lost Time") 
        time.sleep(3)
        focus_control(dlg)


        #     # owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        #     # owner.wait('exists',timeout=0.5)
        #     # ucc = owner.child_window(auto_id="frmUnityClaimClaimant",control_type="Window")
        #     # ucc.wait('exists',timeout=3)
        #     # ucc.set_focus()

        #     owner = desk.window(title_re=r"Subject Line Builder Email Display.*", control_type="Window")
        #     owner.wait("exists", timeout=10)

        #     def get_urs(timeout=20):
        #         def _locate():
        #             hwnd = find_windows(
        #                 title="Unity Referral Source",
        #                 class_name="WindowsForms10.Window.8.app.0.6255dd_r8_ad1",
        #                 top_level_only=False,
        #                 visible_only=False,
        #                 enabled_only=False
        #             )[0]

        #             app = Application(backend="uia").connect(handle=hwnd)
        #             w = app.window(handle=hwnd)
        #             w.wait("exists", timeout=1)
        #             return w

        #         urs = wait_until_passes(timeout, 0.2, _locate)
        #         urs.wait("ready", timeout=timeout)
        #         try:
        #             urs.set_focus()
        #         except Exception:
        #             pass
        #         return urs

        #     urs = get_urs(timeout=20)


        #     # owner = desk.window(title_re=r"Subject Line Builder Email Display*",control_type="Window")
        #     # owner.wait('exists',timeout=3)
        #     # urs = Desktop(backend="uia").window(title_re=r"Unity Referral Source*",control_type="Window")
        #     # urs = Desktop(backend="uia").window(auto_id="frmUnityReferralSource",control_type="Window")
            

        #     # urs.wait('visible ready exists',timeout=3) 
        #     time.sleep(3)
        #     #Validate CB Values
        #     cbContactType = urs.child_window(auto_id="cbContactType", control_type="ComboBox").wrapper_object()
        #     cbContactType.iface_value.SetValue("Customer TCM")
        #     notify("Notice","Please validate if Selected dropdown for Contact Type is Correct.")
        #     time.sleep(3)
        #     rbRefSource = dlg.child_window(auto_id="rbRefSource", control_type="RadioButton").wrapper_object()
        #     rbRefSource.select()
        # else:
        #     rbAdjuster = dlg.child_window(auto_id="rbAdjuster", control_type="RadioButton").wrapper_object()
        #     rbAdjuster.select()

       # assumes you already have: import time, ctypes
# and: from pywinauto import Desktop
# and: from pywinauto.timings import wait_until_passes

        def msgbox(text, title="Debug"):
            ctypes.windll.user32.MessageBoxW(0, str(text), str(title), 0)

        desk = Desktop(backend="uia")

        owner = desk.window(title="Subject Line Builder Email Display", control_type="Window")
        owner.wait("exists ready", timeout=10)
        time.sleep(0.2)

        # rbAdjuster
        if allData['refSource']:
            # IMPORTANT: CLICK instead of Toggle (more like manual)
            try:
                cbReferralSource = owner.child_window(auto_id="cbReferralSource", control_type="CheckBox").wrapper_object()

                # click only if unchecked (avoid accidentally unchecking)
                try:
                    if cbReferralSource.get_toggle_state() != 1:
                        safe_click(cbReferralSource)
                except Exception:
                    safe_click(cbReferralSource)

            except Exception as e:
                msgbox(f"Failed to click cbReferralSource.\n{type(e).__name__}: {e}", "RRS UIA")
                raise

            # let WinForms spawn popup + UIA tree update
            time.sleep(0.6)

            def find_urs_under_owner():
                # Re-acquire owner each retry to avoid stale UIA subtree
                o = desk.window(title="Subject Line Builder Email Display", control_type="Window")

                # small settle each retry
                time.sleep(0.15)

                # Search deeper; filter by control_type in element_info
                for w in o.descendants():
                    try:
                        ei = w.element_info
                        if ei.control_type != "Window":
                            continue

                        title = (w.window_text() or "").strip()
                        autoid = (ei.automation_id or "").strip()

                        if autoid == "frmUnityReferralSource" or title == "Unity Referral Source":
                            return desk.window(handle=w.handle)
                    except Exception:
                        pass

                raise RuntimeError("Unity Referral Source not found under owner yet")

            try:
                urs = wait_until_passes(30, 0.3, find_urs_under_owner)
            except Exception as e:
                # Show what UIA sees under owner (Window nodes only)
                lines = []
                try:
                    o = desk.window(title="Subject Line Builder Email Display", control_type="Window")
                    for w in o.descendants():
                        try:
                            ei = w.element_info
                            if ei.control_type == "Window":
                                lines.append(
                                    f"{hex(w.handle)} | {repr(w.window_text())} | auto_id={ei.automation_id!r} | class={ei.class_name!r}"
                                )
                        except Exception:
                            pass
                except Exception as ee:
                    lines.append(f"<descendants failed: {ee!r}>")

                msgbox(
                    "FAILED to find 'Unity Referral Source' under owner.\n\n"
                    f"Error: {type(e).__name__}: {e}\n\n"
                    "Owner subtree windows:\n" + "\n".join(lines[:80]),
                    "RRS Popup Debug (UIA)"
                )
                raise

            # Wait exists then ready (plus small sleeps)
            urs.wait("exists", timeout=10)
            time.sleep(0.3)
            urs.wait("ready", timeout=10)
            time.sleep(0.2)

            # Now your original UIA code should work:
            cbContactType = urs.child_window(auto_id="cbContactType", control_type="ComboBox").wrapper_object()
            cbContactType.iface_value.SetValue("Customer TCM")
            time.sleep(0.15)

            tbFirstName = urs.child_window(auto_id="tbFirstName", control_type="Edit").wrapper_object()
            tbFirstName.iface_value.SetValue(AdjusterFName)
            time.sleep(0.10)

            tbLastName = urs.child_window(auto_id="tbLastName", control_type="Edit").wrapper_object()
            tbLastName.iface_value.SetValue(AdjusterLName)
            time.sleep(0.10)

            tbEmail = urs.child_window(auto_id="tbEmail", control_type="Edit").wrapper_object()
            tbEmail.iface_value.SetValue(allData['adjEmail'])
            time.sleep(0.10)

            tbPhone = urs.child_window(auto_id="tbPhone", control_type="Edit").wrapper_object()
            tbPhone.iface_value.SetValue(allData['adjPhone'])
            
            btnOK = urs.child_window(auto_id="btnOK", control_type="Button").wrapper_object()
            safe_click(btnOK)

            #Validate CB Values

            rbRefSource = dlg.child_window(auto_id="rbRefSource", control_type="RadioButton").wrapper_object()
            rbRefSource.select()
        else:
            rbAdjuster = dlg.child_window(auto_id="rbAdjuster", control_type="RadioButton").wrapper_object()
            rbAdjuster.select()

        # do no edit beyond this code   
        # rbMed,rbVoc
        if 'full case management' in allData['referralType'].lower() or "one-time rn visit" in allData['referralType'].lower():
            rbMed = dlg.child_window(auto_id="rbMed", control_type="RadioButton").wrapper_object()
            rbMed.select()
        elif "voc" in allData['referralType'].lower():
            rbVoc = dlg.child_window(auto_id="rbVoc", control_type="RadioButton").wrapper_object()
            rbVoc.select()

        # # tbDiagCode - edited
        # tbDiagCode = dlg.child_window(auto_id="tbDiagCode", control_type="Edit").wrapper_object()
        # tbDiagCode.iface_value.SetValue(allData['dxCode'])

        notify("Script Paused","Review SBL fields to ensure accuracy and completeness.\nOnce done, Click OK to build.")
        print(f'Submit Subject Template Builder')
        # btnCreate
        btnCreate = dlg.child_window(auto_id="btnCreate",control_type="Button").wrapper_object()
        safe_click(btnCreate)
        time.sleep(10)

        #Email Display Exit
        focus_control(emaiDisplay)
        btnExit = emaiDisplay.child_window(auto_id="btnExit",control_type="Button").wrapper_object()
        safe_click(btnExit)
        time.sleep(3)
        botStop = False
        # pprint(allData)
    except Exception as ex:
        # print("error occurred: ", ex)
        exc_type, exc_obj, tb = sys.exc_info()
        line_number = tb.tb_lineno
        # driver.execute_script("h$(0);")
        print(f"error occurred: {ex} (line {line_number})")
        botStop=True
        sys.exit()
