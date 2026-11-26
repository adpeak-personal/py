from func import *


# chrome://version/ 에서 '프로필경로' 복사, 난 왜 디폴트만 되지?? 뭔... 딴건 필요 없쓰....


def goScript(getDict):
    wb = load_workbook('./etc/nid.xlsx')
    ex = wb.active
    getTime = str(ex.cell(1, 2).value)

    if getDict['writeVal']:
        try:
            getWriteHour = int(getTime.split(':')[0])
        except:
            pg.alert('예약 시간이 지정되지 않았습니다. 확인해주세요')
            return
    
    now = datetime.now()
    setHour = now.hour
    setHourStr = int(setHour)
    
    if getDict['writeVal']:
        if getWriteHour < setHourStr:
            pg.alert('설정한 시간이 현재 시간보다 이전입니다. 수정해주세요')
            return
    # 글이 너무 짧거나, 이미지가 없는 글 최초 검증 체크!!!!
    
    getCwd = re.sub(r'[\\]', '/', os.getcwd())
    
    dirList = os.listdir(f"{os.getcwd()}\\content")
    chkImgLine = ''
    
    if not dirList:
        pg.alert('컨텐츠가 없습니다. 확인해주세요')
        return
    for dir in dirList:
        getLines = []
        
        try:
            try:
                with open(f'./content/{dir}/content.txt', 'rt', encoding='UTF8') as f:
                    getLines = f.readlines()
            except:
                with open(f'./content/{dir}/content.txt', 'r') as f:
                    getLines = f.readlines()
        except:
            pass
                
        for idx, line in enumerate(getLines):
            if 'img_line' in line:
                
                
                chkImgLine = 'ok'
                imgChk = line.split('|')
                imgName = imgChk[1].replace('\n','')
                
                pngChk = os.path.isfile(f'{getCwd}/content/{dir}/{imgName}.png')
                jpgChk = os.path.isfile(f'{getCwd}/content/{dir}/{imgName}.jpg')
                png2Chk = os.path.isfile(f'{getCwd}/content/{dir}/{imgName}.PNG')
                jpegChk = os.path.isfile(f'{getCwd}/content/{dir}/{imgName}.jpeg')
                
                if not pngChk and not jpgChk and not png2Chk and not jpegChk:
                    pg.alert(f'{dir}폴더 {idx}번째 라인에 이미지 링크 {imgName} 오류!!! 종료!!')
                    sys.exit(0)
                
        
        if not chkImgLine:
            pg.alert('컨텐츠 내에 이미지가 없습니다. 종료합니다!')
            sys.exit(0)
        elif len(getLines) < 10:
            pg.alert('컨텐츠 파일이 없거나, 글이 너무 짧습니다. 종료합니다!')
            sys.exit(0)
            
    
    pg.alert('시작합니다!')
    
    if getDict['nlist'] == 1:
        pg.alert('아이디가 선택되지 않았습니다. 다시 실행해주세요')
        sys.exit(0)
    
    
    exLineNum = getDict['nlist']
    
    
    if getDict['personVal'] == 0 and ex.cell(exLineNum, 3).value is None:
        pg.alert('프로필이 설정되지 않았습니다. 다시 확인해주세요')
        sys.exit(0)
        
    if ex.cell(exLineNum, 4).value is not None:
        pg.alert('이미 작업된 블로그! 작업 안했다면 항목을 지워주세요! 그냥 시작합니다!')
        
        
    ex.cell(exLineNum, 4).value = '작업완료'
    wb.save('./etc/nid.xlsx')
    
    
    
    preIp = ''
    
    while True:
        if getDict['ipval'] == 1 and getDict['personVal'] == 0:
            while True:
                print('아이피 변경 작업 시작!!')
                getIP = changeIp()
                print(getIP)
                
                ipChkCount = 0
                sameIp = ''
                while True:
                    ipChkCount += 1
                    if ex.cell(ipChkCount, 1).value is None:
                        break
                    elif str(ex.cell(ipChkCount, 5).value) == str(getIP):
                        sameIp = 'on'
                        break
                if sameIp == 'on':
                    continue
                else:
                    ex.cell(exLineNum, 5).value = getIP
                    wb.save('./etc/nid.xlsx')
                    break
        
        try:
            
            pcUser = getpass.getuser()
            options = Options()
            
            options = Options()
            
            if getDict['personVal']:
                user_data = f'C:\\Users\\{pcUser}\\AppData\\Local\\Google\\Chrome\\User Data'
                options.add_argument(f"user-data-dir={user_data}")
            else:
                user_data = f'C:\\Users\\{pcUser}\\AppData\\Local\\Google\\Chrome\\User Data\\default'
                options.add_argument(f"user-data-dir={user_data}")
                options.add_argument(f'--profile-directory=Profile {ex.cell(exLineNum, 3).value}')
            
            # 이 아래 부분이 (2줄)이 바뀌었음
            # service = ChromeService(executable_path=ChromeDriverManager().install())
            service = Service(ChromeDriverManager().install())
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(5)

            if getDict['personVal']:
                driver.get('https://www.google.com')
                pg.alert('프로필 체크하기!!')

            driver.get('https://www.naver.com')
            
            driver.set_page_load_timeout(30)
            driver.set_window_size(1100, 800)
            driver.set_window_position(0,0)
            break
        except Exception as e:
            print(e)
            driver.quit()
            pass
    
    
    # if getDict['profileVal'] == 0:
    #     pg.alert('프로필 체크 대기~~~')
    
    # chrome://version
    
    if getDict['middleVal'] == 1:
        pg.alert('로그인을 시작합니다.')
    
    
    while True:
        print('로그인 버튼 클릭하기~~~')
        try:
            wait_float(1.2,1.9)
            loginBtn = driver.find_element(by=By.CSS_SELECTOR, value=".MyView-module__link_login___HpHMW")
            loginBtn.click()
        except:
            pass
        
        try:
            wait_float(0.5,1.2)
            idInputChk = driver.find_element(by=By.CSS_SELECTOR, value="#id_line")
            if idInputChk:
                break
        except:
            pass
        
        
        
    focus_window('로그인')
    wait_float(0.3,0.9)
    while True:
        
        pg.click(250,500)
        inputId = driver.find_element(by=By.CSS_SELECTOR, value="#id")
        inputId.click()
        wait_float(0.3,0.9)
        cb.copy(ex.cell(exLineNum, 1).value)
        wait_float(0.3,0.9)
        pg.hotkey('ctrl', 'a')
        wait_float(0.3,0.9)
        pg.hotkey('ctrl', 'v')
        inputId = driver.find_element(by=By.CSS_SELECTOR, value="#id")
        if inputId.get_attribute('value') != "":
            break
        
    while True:
        inputPw = driver.find_element(by=By.CSS_SELECTOR, value="#pw")
        inputPw.click()
        wait_float(0.3,0.9)
        cb.copy(ex.cell(exLineNum, 2).value)
        wait_float(0.3,0.9)
        pg.hotkey('ctrl', 'a')
        wait_float(0.3,0.9)
        pg.hotkey('ctrl', 'v')
        inputPw = driver.find_element(by=By.CSS_SELECTOR, value="#pw")
        if inputPw.get_attribute('value') != "":
            break
    
    btnLogin = searchElement('.btn_login',driver)
    btnLogin[0].click()
    
    while True:
        try:
            WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#query")))
            break
        except:
            driver.get('https://www.naver.com')
            
    
    
    
    if getDict['middleVal'] == 1:
        chkVal = pg.confirm(text='공감 순방을 진행하겠습니까?', buttons=['go','stop'])
        if chkVal == 'go':
            allowListVisit(driver)
        else:
            pass
    else:
        if getDict['gonggamVal'] == 1:
            allowListVisit(driver)
        else:
            pass
        
    
    if getDict['middleVal'] == 1:
        chkVal = pg.confirm(text='글 작성을 진행하겠습니까?', buttons=['go','stop'])
        if chkVal == 'go':
            writeBlog(driver,getDict['middleVal'],getTime)
        else:
            pass
    else:
        if getDict['writeVal'] == 1:
            writeBlog(driver,getDict['middleVal'],getTime)
        else:
            pass
        
    if getDict['middleVal'] == 1:
        chkVal = pg.confirm(text='이웃 순방을 진행 하시겠습니까?', buttons=['go','stop'])
        if chkVal == 'go':
            visitNeighborWork(driver)
        else:
            pass
    else:
        if getDict['neighborVal'] == 1:
            visitNeighborWork(driver)
        else:
            pass

    
    if getDict['middleVal'] == 1:
        chkVal = pg.confirm(text='이웃 추가를 진행 하시겠습니까?', buttons=['go','stop'])
        if chkVal == 'go':
            addNeighborWork(driver)
        else:
            pass
    else:
        if getDict['neighborAddVal'] == 1:
            addNeighborWork(driver)
        else:
            pass
    
    
    for i in range(3):
        fr = 1600    # range : 37 ~ 32767
        du = 500     # 1000 ms ==1second
        sd.Beep(fr, du)
        
    pg.alert('종료합니다!!')
    sys.exit(0)





# ***************************************************************


