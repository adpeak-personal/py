from func import *

test = None
# test = "ok"

def trfficScript(getDict):

    workType = {}
    siteLink = "https://happy-toad2.shop"

    success, res = request_safely_get(f"{siteLink}/api/v7/res_traffic_work/get_webclass")
    workType['web_class'] = res['web_class']
    
    if getDict['group_val'] == '' or getDict['group_val'] is None:
        pg.alert('그룹을 선택 해 주세요!')
        sys.exit()
    else:
        workType['pr_group'] = getDict['group_val']

    newIp = ""
    oldIp = ""

    # 현재 날짜와 시간을 얻기 (경과된 시간을 찾기 위함)
    now = datetime.now()
    # 문자열 형식으로 변환
    date_string = now.strftime("%Y-%m-%d %H:%M:%S")

    if os.path.isfile('./work_time.txt') == False:
        with open('./work_time.txt', 'w') as file:
            file.write(f"{date_string} 시작하기!!")

    with open('./pc_id.txt', 'r') as file:
        pcId = file.read()

    workType['pr_work_type'] = ''
    workInfo = {} # 1회 돌아갈때 작업 할 정보 담는 객체
    while True:

        if getDict['workTypeVal'] == 'mix':
            # PC랑 모바일 한번씩 번갈아가면서 돌기!! (무한 루프 돌면서 바뀜)
            if workType['pr_work_type'] is None or workType['pr_work_type'] == "" or workType['pr_work_type'] == 'pc':
                workType['pr_work_type'] = 'mobile'
            else:
                workType['pr_work_type'] = 'pc'
        elif getDict['workTypeVal'] == 'pc':
            workType['pr_work_type'] = 'pc'
        elif getDict['workTypeVal'] == 'mobile':
            workType['pr_work_type'] ='mobile'
        
        print('전체 while문 돌기!!!!')
        # 전체 try / except!!! 작업 중간에 문제 생기면 창 닫아버림!!!!
        try:

            start_time = time.time()
            start_time_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
            with open('./work_time.txt', 'a') as file:
                file.write(f"시작시간 : {start_time_str} ")

            driver = ""
            retryCount = 0
            while True:
                retryCount += 1
                # 아이피 변경 부분!
                if getDict['ipval'] and retryCount == 1:
                    getIp = changeIp()
                    newIp = getIp
                    print(f"oldIp : {oldIp} / newIp : {newIp}")
                    if oldIp == newIp:
                        continue
                    oldIp = newIp

                    print('멈추는 경우? 왜?!')
                # 아이피 변경 부분 끝!!

                # 크롬 접속!! (기본 5초 주고 5초 내 접속 못하면 아이피 변경으로 돌아가기~~)
                if workType['pr_work_type'] == 'pc':
                    try:
                        # pcUser = getpass.getuser()
                        user_data_dir = tempfile.mkdtemp(prefix="selenium_profile_")
                        options = Options()
                        options.page_load_strategy = 'eager'
                        options.add_argument(f"--user-data-dir={user_data_dir}")  # 프로필 분리(누수 ↓)
                        service = Service()  # chromedriver PATH 잡혀있다고 가정
                        options.add_experimental_option("excludeSwitches", ["enable-automation"])
                        driver = webdriver.Chrome(options=options)
                        driver.set_page_load_timeout(15)

                        driver.get('https://www.naver.com')
                        
                        driver.set_window_size(1300, 800)
                        driver.set_window_position(0,0)
                        
                        break
                    except Exception as e:
                        print(e)
                        print('크롬 창 오픈 실패!!')
                        driver.quit()
                        pass
                else:
                    try:
                        res = requests.get(f"{siteLink}/api/v7/res_traffic_work/get_user_agent").json()
                        print(res['user_agent_info']['ua_content'])
                        if res['status'] == True and res['user_agent_info']['ua_content'] is not None:
                            userAgentInfo = res['user_agent_info']['ua_content']
                            try:
                                user_data_dir = tempfile.mkdtemp(prefix="selenium_profile_")
                                options = Options()
                                options.page_load_strategy = 'eager'
                                options.add_argument(f"--user-data-dir={user_data_dir}")  # 프로필 분리(누수 ↓)
                                service = Service()  # chromedriver PATH 잡혀있다고 가정
                                options.add_argument(f'user-agent={userAgentInfo}')

                                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                                options.add_experimental_option("useAutomationExtension", False)
                                driver = webdriver.Chrome(options=options)
                                driver.set_page_load_timeout(15)
                                driver.get('https://www.naver.com')
                                driver.set_window_size(1000, 800)
                                driver.set_window_position(0,0)
                                break
                            except Exception as e:
                                print(e)
                                print('크롬 창 오픈 실패!!')
                                driver.quit()
                                pass

                    except Exception as e:
                        print(str(e))
                        print('프로필 정보 불러오기 오류!!')
                        continue

            
            # >>>>>>>>>>>>>>> 작업 라인 START!!!!!!

            # while True:
            #     x, y = pg.position()  # 현재 마우스 좌표 (x, y)
            #     print(f"X: {x}, Y: {y}", end="\r")  # 같은 줄에서 갱신 출력
            #     time.sleep(0.1)  # 0.1초마다 갱신
            #     pg.alert('잠깐!')

            # 네이버 메인 포커스! 최초 1회 (마우스 클릭을 위해서)
            errCount = 0
            while True:
                errCount += 1
                if errCount > 5:
                    driver.get('https://www.naver.com')
                    errCount = 0
                    wait_float_timer(2,3)
                    continue
                wait_float_timer(0,1)
                pg.moveTo(20,110)
                pg.leftClick()
                print('검색 start!!')
                focusChk = focus_target_chrome(driver, ['NAVER'])
                if focusChk:
                    break
                else:
                    wait_float(1.2,1.9)
                    pg.press('F5')

            activeArrLengthArr = [6,7]
            activeArrInnerArr = [3,4]
            workArr = create_active_array(activeArrLengthArr, activeArrInnerArr)
            print(workArr)

            if test:
                workArr = ['realWork','realWork']

            # 핵심 부분!!!
            for work in workArr:
                print(work)
                if work == 'notWork':
                    # not work 불러오기!!!!
                    success, res = request_safely_get(f"{siteLink}/api/v7/res_traffic_work/load_notwork")
                    workInfo = res['get_keyword']
                    print('네이버 검색 시작!')

                    naverSearch(driver, workInfo['pk_content'])
                    # not_work 작업!!! 아무거나 하나 클릭하기!!
                    if workType['pr_work_type'] == 'pc':
                        clickScrollOtherPC(driver,workInfo['pk_content'])
                        print('PC 클릭 및 스크롤 완료!')
                        backToSearchPC(driver,workInfo['pk_content'])
                        print('원래 창 복귀 완료!')
                    else:
                        clickScrollOtherMobile(driver,workInfo['pk_content'])
                        print('모바일 클릭 및 스크롤 완료!')
                        backToSearchMobile(driver,workInfo['pk_content'])
                        print('원래 창 복귀 완료!')
                elif work == 'work':

                    while True:
                        success, res = load_notwork_safely_post(f"{siteLink}/api/v7/res_traffic_work/load_work", {'group' : workType['pr_group']})

                        print('load work 불러오기 값!!! ')
                        print(success)
                        print(res)
                        try:
                            if success == True and res['get_work'] != {}:
                                break
                        except:
                            pass

                    workInfo = res['get_work']
                    print('여기 오류 전임?')
                    naverSearch(driver, workInfo['st_subject'])

                    # not_work 작업!!! 아무거나 하나 클릭하기!!
                    if workType['pr_work_type'] == 'pc':
                        clickScrollOtherPC(driver,workInfo['st_subject'])
                        print('PC 클릭 및 스크롤 완료!')
                        backToSearchPC(driver,workInfo['st_subject'])
                        print('원래 창 복귀 완료!')

                        rateRes = searchContentRate(driver, workType, workInfo, 'view', 'pc')
                    else:
                        clickScrollOtherMobile(driver,workInfo['st_subject'])
                        print('모바일 클릭 및 스크롤 완료!')
                        backToSearchMobile(driver,workInfo['st_subject'])
                        print('원래 창 복귀 완료!')

                        rateRes = searchContentRate(driver, workType, workInfo, 'view')
                        print(rateRes)
                        print(workInfo['st_id'])

                    success, res = load_notwork_safely_post(f"{siteLink}/api/v7/res_traffic_work/update_traffic_work", {'status' : rateRes['status'], 'st_id' : workInfo['st_id'], 'rate' : rateRes['rate']})

                elif work == 'realWork':

                    while True:
                        success, res = load_notwork_safely_post(f"{siteLink}/api/v7/res_traffic_work/load_realwork", {'group' : workType['pr_group'], 'work_type' : workType['pr_work_type']})

                        print('load real work 불러오기 값!!! ')
                        print(success)
                        print(res)

                        try:
                            if success == True and res['get_realwork'] != {}:
                                break
                        except:
                            pass

                    workInfo = res['get_realwork']
                    print('여기 오류 전임?')
                    naverSearch(driver, workInfo['st_subject'])

                    # not_work 작업!!! 아무거나 하나 클릭하기!!
                    if workType['pr_work_type'] == 'pc':
                        clickScrollOtherPC(driver,workInfo['st_subject'])
                        print('PC 클릭 및 스크롤 완료!')
                        backToSearchPC(driver,workInfo['st_subject'])
                        print('원래 창 복귀 완료!')

                        rateRes = searchContentRate(driver, workType, workInfo, 'click', 'pc')
                    else:
                        clickScrollOtherMobile(driver,workInfo['st_subject'])
                        print('모바일 클릭 및 스크롤 완료!')
                        backToSearchMobile(driver,workInfo['st_subject'])
                        print('원래 창 복귀 완료!')

                        rateRes = searchContentRate(driver, workType, workInfo, 'click')
                        print(rateRes)
                        print(workInfo['st_id'])

                    success, res = load_notwork_safely_post(f"{siteLink}/api/v7/res_traffic_work/update_traffic_realwork", {'work_type': workType['pr_work_type'] ,'status' : rateRes['status'], 'st_id' : workInfo['st_id'], 'rate' : rateRes['rate']})

                    


            # 작업 완료 체크 하기!!
            success, res = request_safely_get(f"{siteLink}/api/v7/res_traffic_work/update_last_traffic?sl_id={pcId}")

            # 시간 기록
            end_time = time.time()
            end_time_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
            elapsed_time = end_time - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)

            try:
                with open('./work_time.txt', 'a', encoding='utf-8') as file:
                    file.write(f"종료시간 : {end_time_str} / 프로그램 실행 시간: {minutes}분 {seconds}초\n")
                print(f'[INFO] 작업 시간 기록 완료: {minutes}분 {seconds}초')
            except Exception as e:
                print(f'[ERROR] 파일 저장 실패: {str(e)}')

            close_driver(driver, service, user_data_dir)

            # 코드 실행 라인
        except Exception as e:
            print('전체 오류임?')
            print(str(e))
            if driver:
                driver.quit()
            pass