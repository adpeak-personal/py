from func import *

def goScript(getDict):

    siteLink = "https://happy-toad2.shop"
    # siteLink = "http://localhost:3020"
    client_id = "UJdG7deo1wx_DlrtNb86"
    client_secret = "z3g0uceauU"

    problemReset = True
    tCount = 0
    while True:

        if getDict['test_val']:
            tCount += 1
            if tCount > 1:
                pg.alert('테스트 작업 완료 함?!')


        driverTitle = ""

        now = datetime.datetime.now().time()
        if datetime.time(0, 10) <= now <= datetime.time(0, 30):
            print("지금 실행해!")

            problemReset = True

        if problemReset == True:
            print("problem 리셋하기!!!!!")
            while True:
                try:
                    wait_float(0.3,0.5)
                    getInfo = requests.get(f"{siteLink}/api/v7/res/reset_problem").json()
                    if getInfo['status'] == True:
                        problemReset = False
                        break
                except Exception as e:
                    print(str(e))


        getInfo = ''

        if getDict['test_val']:
            fCount = 0
            while True:
                fCount += 1
                if fCount > 3:
                    alert('테스트 작업이 존재하지 않습니다.')
                    sys.exit(0)
                try:
                    wait_float(0.3,0.5)
                    getInfo = requests.get(f"{siteLink}/api/v7/res/get_backlink_test_data").json()
                    print(f"API 받아오기 완료! 정보는? {getInfo}")

                    if getInfo['status'] == True:
                        print('이제 break 해야지!!')
                        break
                except Exception as e:
                    print(str(e))
            print('API 정보 받고 나왔따!!!')
        else:
            while True:
                try:
                    wait_float(0.3,0.5)
                    getInfo = requests.get(f"{siteLink}/api/v7/res/get_backlink_data").json()
                    print(f"API 받아오기 완료! 정보는? {getInfo}")

                    if getInfo['status'] == True:
                        break
                except Exception as e:
                    print(str(e))


        workInfo = getInfo['get_work']

        print(f"작업 정보 : {workInfo}")


        # 접속을 먼저 한 다음에 글쓰기가 가능한 상태인지 체크하기!!!!!
        session = requests.Session()
        domain = workInfo['bl_link']
        board = workInfo['bl_board']
        login_url = f"{domain}/bbs/login_check.php"
        payload = {
            "mb_id": workInfo['bl_siteid'],
            "mb_password": workInfo['bl_sitepwd']
        }

        cookies = {}


        cookieStatus = False
        for i in range(5):
            print(f"쿠키 시도 {i} 번째")
            try:
                res = session.post(login_url, data=payload, verify=False)
                print(1)
                print(res)
                cookies = session.cookies.get_dict()
                print(2)
                print("cookies : ", cookies)
                cookieStatus = True
                break
            except Exception as e:
                print(str(e))
        
        if cookieStatus == False:
            while True:
                try:
                    getStatus = requests.post(f"{siteLink}/api/v7/res/update_faulty_site", {"bl_id" : workInfo["bl_id"], "value" : "false", "message" : "로그인 불가!"}).json()
                    if getStatus['status'] == True:
                        break
                except Exception as e:
                    print(str(e))
            continue
            

        # Step 2: Selenium 시작
        options = Options()
        driver = webdriver.Chrome()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        driver.set_page_load_timeout(15)

        try:
            driver.get(domain)
        except:
            driver.quit()
            continue

        try:
            # Step 3: 쿠키 삽입
            for name, value in cookies.items():
                driver.add_cookie({"name": name, "value": value})
        except:
            pass

        if getDict['test_val']:
            getcookies = driver.get_cookies()
            for cookie in getcookies:
                print(cookie)
            
            pg.alert('보쟈 ㅠ')


        

        try:
            # Step 4: 로그인된 상태로 글쓰기 페이지 열기
            driver.get(f"{domain}/bbs/write.php?bo_table={board}")
            wait_float(1.2,1.9)
        except:
            driver.quit()
            continue

        print('글쓰기 페이지 들어옴!!!')

        try:
            WebDriverWait(driver, 2).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            if alert:
                alert.accept()

                while True:
                    try:
                        getStatus = requests.post(f"{siteLink}/api/v7/res/update_faulty_site", {"bl_id" : workInfo["bl_id"], "value" : "false", "message" : "게시판 짤림!"}).json()
                        if getStatus['status'] == True:
                            break
                    except Exception as e:
                        print(str(e))

                driver.quit()
                continue

        except Exception as e:
            print('에러가 다긴 나는거지?!')
            print("✅ Alert 창 없음")

        current_url = driver.current_url
        chkDomain = extract_domain(domain)

        print(f"현재 URL : {current_url}")
        print(f"도메인 : {domain}")
        
        # 주소창에 도메인이 없으면 허용 접속량이 초과된 상태!!
        if chkDomain not in current_url:
            while True:
                try:
                    getStatus = requests.post(f"{siteLink}/api/v7/res/update_faulty_site", {"bl_id" : workInfo["bl_id"], "value" : "problem", "message" : "접속량 초과! 추가 확인!"}).json()
                    if getStatus['status'] == True:
                        break
                except Exception as e:
                    print(str(e))
            driver.quit()
            continue
        # 주소창에 write가 없음 즉, 글을 못쓰는 상태이므로 사이트 짤림!!
        elif "write" not in current_url:
            while True:
                try:
                    getStatus = requests.post(f"{siteLink}/api/v7/res/update_faulty_site", {"bl_id" : workInfo["bl_id"], "value" : "false", "message" : "게시판 짤림!"}).json()
                    if getStatus['status'] == True:
                        break
                except Exception as e:
                    print(str(e))
            driver.quit()
            continue

        if getDict['test_val']:
            pg.alert(cookies)
        if not cookies:
            while True:
                try:
                    getStatus = requests.post(f"{siteLink}/api/v7/res/update_faulty_site", {"bl_id" : workInfo["bl_id"], "value" : "false", "message" : "로그인 불가!"}).json()
                    if getStatus['status'] == True:
                        break
                except Exception as e:
                    print(str(e))
            continue

        # 타이틀 값 넣어주기!!
        while True:
            driverTitle = driver.title
            if driverTitle != "":
                break


        # 만약 화면에 캡챠가 있으면 위 방식으로 로그인이 안됨! 수종 로그인 시도!!
        captchaErrCount = 0
        captchaErrStatus = False
        while True:
            captchaErrCount += 1
            if captchaErrCount > 3:
                break
            # 다 완료 되었는데 캡챠가 있으면 로그인 불가한 비 정상 사이트로 간주 continue!!
            try:
                captcha_key = driver.find_elements(by=By.CSS_SELECTOR, value="#captcha_key")
                if len(captcha_key) > 0:
                    print('캡챠가 있음!! 비정상 사이트 처리!!!')
                    captchaErrStatus = True
                else:
                    captchaErrStatus = False
                    print('캡챠 없음!! 정상 사이트 처리!!!')
                    break
            except:
                pass

            # 로그인 시도!!
            try:
                driver.get(f"{domain}/bbs/login.php")
                wait_float(1.2,1.9)
                mbId = driver.find_element(By.CSS_SELECTOR, '[name="mb_id"]')
                mbId.send_keys(workInfo['bl_siteid'])
                wait_float(0.5,1.2)
                mbPwd = driver.find_element(By.CSS_SELECTOR, '[name="mb_password"]')
                mbPwd.send_keys(workInfo['bl_sitepwd'])
                wait_float(0.5,1.2)

                submit_buttons = driver.find_elements(By.CSS_SELECTOR, '[type="submit"]')
                login_buttons = []
                for btn in submit_buttons:
                    val = btn.get_attribute("value") or ""
                    text = btn.text or ""
                    if "로그인" in val or "로그인" in text:
                        login_buttons.append(btn)

                for btn in login_buttons:
                    try:
                        btn.click()
                        break
                    except:
                        pass

            except:
                pass

            # 로그인 완료 되면 글쓰기 페이지로 이동!
            wait_float(1.2,1.9)
            driver.get(f"{domain}/bbs/board.php?bo_table={board}")
            wait_float(1.2,1.9)
            driver.get(f"{domain}/bbs/write.php?bo_table={board}")
            wait_float(1.2,1.9)

        if captchaErrStatus == True:

            while True:
                try:
                    getStatus = requests.post(f"{siteLink}/api/v7/res/update_faulty_site", {"bl_id" : workInfo["bl_id"], "value" : "false", "message" : "로그인 불가!"}).json()
                    if getStatus['status'] == True:
                        break
                except Exception as e:
                    print(str(e))
            driver.quit()
            continue



        # 타겟 링크 구하기 GOGO!!
        targetList = ''
        while True:
            
            try:
                wait_float(0.3,0.5)
                targetInfoRes = requests.get(f"{siteLink}/api/v7/res/get_target_data").json()
                print(f"API 받아오기 완료! 정보는? {targetInfoRes}")

                if targetInfoRes['status'] == True:
                    print('이제 break 해야지!!')
                    break
            except Exception as e:
                print(str(e))
                pass

        print('나왔어!!')
        # 타겟 링크 A태그 2개 배열로 변환!!
        targetList = targetInfoRes['target_list']
        linkList = []
        for target in targetList:
            linkTag = f"<a href='{target['tg_link']}' target='_blank'>{target['tg_keyword']}</a>"
            linkList.append(linkTag)

        # 글 따기 작업 GOGO!!!
        article = ""
        while True:
            print('글 따기 중.....')
            while True:
                wait_float(0.5,0.9)
                newsTopicList = ["뉴스", "이슈", "갤럭시", "애플", "삼성", "아이폰", "농구", "축구", "야구", "연예", "드라마"]
                newsTopic = newsTopicList[random.randrange(0, len(newsTopicList))]
                newsDict = getNewsContent(siteLink,client_id, client_secret, newsTopic)

                if newsDict == False:
                    continue

                try:
                    resSubject = replaceText(newsDict['title'])
                    articleTemp = getArticleContent(newsDict["link"])
                except:
                    continue

                try:
                    if articleTemp is not None:
                        article = article + articleTemp
                except Exception as e:
                    print(str(e))
                    pass


                if len(article) > 1500:
                    break
                # 딴 글 가지고 안에 링크 넣기!!!!!
            
            try:
                resultStr = insert_randomly(article, linkList)

                # print("resSubject : ")
                # print(resSubject)
                # print("resultStr : ")
                # print(resultStr)
                break
                
            except Exception as e:
                print(str(e))
                continue

        # 글 따기 작업 끝!!!

        
        


        # 아래는 그누보드 글 쓰기!!!! 이제 시작하기!!!!!!!!!!!

        # 컨텐츠 넣기!!!

        subjectVal = ""
        subjectErrCount = 0
        subjectErrStatus = False
        while True:
            subjectErrCount += 1
            if subjectErrCount > 10:
                subjectErrStatus = True
                break

            print('제목쓰기 에러?!')
            focus_window([driverTitle,"글쓰기"])
            try:
                driver.find_element(By.NAME, "wr_subject").send_keys(resSubject)
            except:
                pass

            try:
                wait_float(0.3,0.9)
                subjectVal = driver.find_element(By.NAME, "wr_subject").get_attribute('value')

                if subjectVal != "":
                    print(subjectVal)
                    break
            except:
                subjectVal = ""
                pass

            wait_float(0.5,0.9)
        

        print('나옴?!?!?!')
        # 페이지 로딩이 잠시 지연되었습니다~ 이러면서 이상하게 뜰때 있음 그럼 그냥 패스~
        if subjectErrStatus == True:
            driver.quit()
            continue

        # 제목 작성 끝~~~~~~~~~~~~~~~~~~~~~~~

        # 에디터 유무에 따라 글쓰기 반영!!
        editorChk = False
        try:
            wait_float(0.5,1.2)
            chkEditor = driver.find_element(by=By.CSS_SELECTOR, value=".smarteditor2")
            if chkEditor:
                editorChk = True

        except Exception as e:
            if 'Timed out' in str(e):
                memoryErrStatus = True

        
        if editorChk:
            while True:
                focus_window([driverTitle,"글쓰기"])
                print('에디터 O 글 작성 부분!!!')

                try:
                    # 사이트 별 특이사항 실행!!!
                    if workInfo['bl_add_script'] is not None:
                        driver.execute_script(workInfo['bl_add_script'])
                except:
                    pass


                try:
                    wait_float(0.5,1.2)
                    firstIframe = driver.find_element(by=By.CSS_SELECTOR, value="iframe")
                    driver.switch_to.frame(firstIframe)
                    wait_float(0.3,0.9)
                    pg.moveTo(400,500)
                    pg.scroll(-50)

                    se2_to_editor_btn = driver.find_element(by=By.CSS_SELECTOR, value=".se2_to_editor")
                    se2_to_editor_btn.click()

                    se2_to_html_btn = driver.find_element(by=By.CSS_SELECTOR, value=".se2_to_html")
                    se2_to_html_btn.click()
                    wait_float(0.3,0.9)
                    pg.hotkey('ctrl','a')
                    pg.press('delete')
                    wait_float(0.3,0.9)
                    cb.copy(resultStr)
                    pg.hotkey('ctrl','v')
                    wait_float(0.3,0.9)
                    driver.switch_to.default_content()
                    break
                except Exception as e:
                    driver.switch_to.default_content()
                    pg.moveTo(10,400)
                    for i in range(10):
                        pg.scroll(200)
                    print(str(e))
        else:

            while True:
                focus_window([driverTitle,"글쓰기"])
                print('에디터 X 글 작성 부분!!!')

                try:
                    # 사이트 별 특이사항 실행!!!
                    if workInfo['bl_add_script'] is not None:
                        driver.execute_script(workInfo['bl_add_script'])
                except Exception as e:
                    pass


                try:
                    # html2 input 태그 있으면 그냥 지워버리고 만들기!!
                    htmlChangeScript = """
                        var elementToDelete = document.getElementById("html");
                        console.log(elementToDelete)
                        if(elementToDelete){
                            elementToDelete.parentNode.removeChild(elementToDelete);
                        }
                        const formElement = document.querySelector('#fwrite')
                        const inputElement = document.createElement("input");
                        inputElement.type = "hidden";
                        inputElement.name = "html";
                        inputElement.id = "html";
                        inputElement.value = "html2";
                        inputElement.classList.add('selec_chk')
                        
                        const firstChild = formElement.firstChild;
                        formElement.insertBefore(inputElement, firstChild);
                    """

                    driver.execute_script(htmlChangeScript)
                except:
                    pass

                try:
                    contentArea = driver.find_element(By.NAME, "wr_content")

                    contentAreaTemp = driver.find_elements(by=By.CSS_SELECTOR, value="#w_desc")
                    if len(contentAreaTemp) != 0:
                        contentAreaTemp[0].click()
                        pg.hotkey('ctrl','a')
                        pg.press('delete')
                        wait_float(0.3,0.9)
                        cb.copy(resultStr)
                        pg.hotkey('ctrl','v')
                        wait_float(0.3,0.9)
                    

                    contentValue = contentArea.get_attribute("value")
                    if contentValue:
                        break
                    contentArea.click()
                    pg.hotkey('ctrl','a')
                    pg.press('delete')
                    wait_float(0.3,0.9)
                    cb.copy(resultStr)
                    pg.hotkey('ctrl','v')
                    wait_float(0.3,0.9)

                except:
                    pass

        


        errCount = 0
        while True:
            errCount = errCount + 1
            if errCount > 10:
                print('에러 무리하고 다음거!')
                break
            print('여기 도는거지?!??!!')


            try:
                submitBtns = driver.find_elements(by=By.CSS_SELECTOR, value="#btn_submit")
                print(submitBtns)
                print(len(submitBtns))
            except:
                pass

            
            try:
                wait_float(0.5,0.9)
                submitBtn = driver.find_element(by=By.CSS_SELECTOR, value="#btn_submit")
                submitBtn.click()
            except Exception as e:
                print(str(e))
                pass
            wait_float(1.2,1.9)


            try:
                WebDriverWait(driver, 2).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                if alert:
                    print('alert 있어?!')
                    alert.accept
                    break
            except:
                print("✅ Alert 창 없음")
                pass

            current_url = driver.current_url
            print(current_url)

            if "write" not in current_url:
                wait_float(1.5,2.2)
                break
            pg.moveTo(400,500)
            pg.scroll(-100)

        if getDict['test_val']:
            pg.alert('글 작성 완료 체크 확인!!')
        
        pc_id = None
        while True:
            print("여기서 에러나?")
            if pc_id is not None:
                break
            try:
                with open(f'./id.txt', 'rt', encoding='UTF8') as f:
                    pc_id = f.read()
            except:
                pass

            try:
                with open(f'./id.txt', 'r') as f:
                    pc_id = f.read()
            except:
                pass

        # #bo_v_con // #bo_v_atc
        while True:
            try:
                getStatus = requests.post(f"{siteLink}/api/v7/res/update_last_backlink_work", {"pc_id" : pc_id}).json()
                if getStatus['status'] == True:
                    if getDict['test_val']:
                        pg.alert('최종 업데이트 체크!!')
                    break
            except Exception as e:
                print(str(e))

        wait_float(1.2,1.9)
        driver.quit()




def joinScript(getdict):

    siteLink = "https://happy-toad2.shop"
    # siteLink = "http://localhost:3020"

    id = "ridebbuu"
    pwd = "1324qewr!"


    while True:
        join_info = {}

        while True:

            try:
                getJoinInfo = requests.get(f"{siteLink}/api/v7/res/get_join_data").json()

                if getJoinInfo['status'] == "complete":
                    pg.alert('작업 완료!')
                    sys.exit(0)
                elif getJoinInfo['status'] == True:
                    break
            except Exception as e:
                print(str(e))
        
        join_info = getJoinInfo['join_info']
        print(join_info)

        # Step 2: Selenium 시작
        options = Options()
        driver = webdriver.Chrome()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        driver.set_page_load_timeout(15)

        joinPage = f"{join_info['bl_link']}/bbs/register.php"
        driver.get(joinPage)

        errCount = 0
        while True:

            try:
                print('회원 가입 바로 전 돌기!')
                errCount += 1
                if errCount > 2:
                    pg.alert('수동 진행 해주세요!')
                    break
                try:
                    labels = driver.find_elements(by=By.CSS_SELECTOR, value="label")
                    for label in labels:
                        try:
                            forVal = label.get_attribute("for")
                            print(forVal)
                            if forVal == "agree11" or forVal == "agree21":
                                label.click()
                        except:
                            pass
                except:
                    pass

                try:
                    btns = driver.find_elements(by=By.CSS_SELECTOR, value="button[type='submit']")
                    for btn in btns:
                        if "가입" in btn.text:
                            btn.click()
                except:
                    pass

                wait_float(1.2,1.9)
                pg.press('enter')

                if "_form" in driver.current_url:
                    break
            
            except:
                pass


        inputList = [
            {"name" : "#reg_mb_id", "val" : "ridebbuu"},
            {"name" : "#reg_mb_password", "val" : "1324qewr!"},
            {"name" : "#reg_mb_password_re", "val" : "1324qewr!"},
            {"name" : "#reg_mb_name", "val" : "라이더"},
            {"name" : "#reg_mb_nick", "val" : "라이더"},
            {"name" : "#reg_mb_email", "val" : "ridebbuu@naver.com"},

        ]

        for input in inputList:
            print(f"{input['name']} 입력 GO!")
            inputValue(driver, input['name'], input['val'])

        while True:
            if "register" in driver.current_url:
                pg.alert("보안 문자 및 회원가입 버튼 클릭 후 눌러주세요!")
            else:
                break

        while True:
            try:
                wait_float(0.3,0.5)
                res = requests.post(f"{siteLink}/api/v7/res/join_success", {"bl_id" : join_info['bl_id']}).json()
                if res['status'] == True:
                    driver.quit()
                    break
            except Exception as e:
                print(str(e))


def inputValue(driver, val, key):

    status = True
    errCount = 0
    while True:
        errCount += 1
        if errCount > 10:
            status = False
            break
        try:
            input = driver.find_element(by=By.CSS_SELECTOR, value=val)
            input.send_keys(key)
        except:
            pass

        try:
            input = driver.find_element(by=By.CSS_SELECTOR, value=val)
            if input.get_attribute('value'):
                break
        except:
            pass
    
    return status