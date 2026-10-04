from func import *

def goScript():

    idWb = load_workbook('./etc/id_list.xlsx')
    idEx = idWb.active

    bandPath = './etc/band_list.xlsx'
    bandWb = load_workbook(bandPath)
    baneEx = bandWb.active

    bandCount = 1 # 밴드 카운트는 1로 시작, 작업 시간에 따라서 변경될 수 있음
    
    getCwd = re.sub(r'[\\]', '/', os.getcwd())

    savedProfile = ""
    while True:
        try:
            with open(f'{getCwd}/etc/profile.txt', 'rt', encoding='UTF8') as f:
                savedProfile = f.read()
        except:
            pass

        try:
            with open(f'{getCwd}/etc/profile.txt', 'r') as f:
                savedProfile = f.read()
        except:
            pass

        if savedProfile != "":
            break

    idCount = 1
    while True:
        idCount += 1
        chkId = idEx.cell(idCount,4).value
        if chkId is None:
            break

    
    pg.alert(f'{idCount - 1}번째 아이디 부터 시작합니다!')
    idCount = idCount - 1
    while True:
        idCount += 1
        id = idEx.cell(idCount,1).value
        pwd = idEx.cell(idCount,2).value
        profile = idEx.cell(idCount,3).value
        onlyJoin = idEx.cell(idCount,5).value
        if id is None:
            pg.alert('작업 완료! 종료합니다.')
            sys.exit(1)

        pcUser = getpass.getuser()

        options = Options()
        user_data = f'C:\\Users\\{pcUser}\\AppData\\Local\\Google\\Chrome\\User Data\\default'
        options.add_argument(f"user-data-dir={user_data}")
        options.add_argument(f'--profile-directory=Profile {profile}')
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.set_window_size(1200, 850)
        driver.set_window_position(0,0)

        driver.get('https://band.us')

        naverLogin(driver, id, pwd)


        wait_float(1.5, 2.3)

        # 로그인 완료 되었으면 2시간동안 밴드 돌기!!

        start_time = datetime.now()
        limit = timedelta(hours=1, minutes=50)  # 1시간 50분
        # limit = timedelta(hours=1)
        while True:

            bandCount += 1
            if baneEx.cell(bandCount,2).value is not None:
                continue

            # 경과 시간 계산
            elapsed = datetime.now() - start_time

            print(f'경과 시간 : {elapsed}')

            # 종료 조건
            if elapsed >= limit:
                idEx.cell(idCount,4).value = 'ok'
                idWb.save('./etc/id_list.xlsx')
                print("⏰ 1시간 50분이 지나서 종료합니다.")
                driver.quit()
                bandCount = 1
                break

            workBandLink = baneEx.cell(bandCount,1).value

            # onedayLimitChk 가 True 면 처음으로 돌아가기!!

            driver.get(workBandLink) # 작업 할 밴드로 이동!

            try:
                pg.moveTo(650, 160, duration=0.2)
                pg.leftClick()
            except:
                pass
            bandStatus = {'status' : True, 'message' : ""}
            bandStatus = joinband(driver, savedProfile, bandStatus)

            if bandStatus['status'] == False:

                if bandStatus['message']:
                    baneEx.cell(bandCount,2).value = bandStatus['message']
                    bandWb.save('./etc/band_list.xlsx')
                    continue
                elif onlyJoin is not None:
                    bandCount = 1
                    idEx.cell(idCount,4).value = 'ok'
                    idWb.save('./etc/id_list.xlsx')
                    driver.quit()
                    break
                else:
                    # 더이상 밴드 가입이 안됨! bandCount 초기화 해서 다시 시작!!
                    bandCount = 1
                    continue

            if onlyJoin is not None:
                continue

            try:
                pg.moveTo(650, 160, duration=0.2)
                pg.leftClick()
            except:
                pass
            # 가장 최신 글이 내 글인지 체크!!

            latestPostChkBool = latestPostChk(driver)
            if latestPostChkBool:
                continue

            deleteLatestPost(driver)


            try:
                pg.moveTo(650, 160, duration=0.2)
                pg.leftClick()
            except:
                pass

            bandWritePost(driver)

            wait_float(30.0, 40.0)







def goScriptCaptureWhile():
    pg.alert('sdfljasldfjlaisjdf')