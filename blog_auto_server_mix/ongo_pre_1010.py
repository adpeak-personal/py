from func import *
from dotenv import load_dotenv

# chrome://version/ 에서 '프로필경로' 복사, 난 왜 디폴트만 되지?? 뭔... 딴건 필요 없쓰....


def goScript(getDict):

    load_dotenv()
    openApiKey = os.getenv("OPEN_API_KEY")

    # siteLink = "http://localhost:3020"
    siteLink = "https://happy-toad2.shop"

    if getDict['loginChkVal']:
        if getDict['directVal'] == '':
            pg.alert('방향 설정을 해주세요')
            sys.exit(1)

    blogWb = load_workbook('./etc/blog_work.xlsx')
    blogEx = blogWb.active

    

    newIp = ""
    oldIp = ""

    now = datetime.now()
    setHour = now.hour
    setHourStr = int(setHour)
    
    # 글이 너무 짧거나, 이미지가 없는 글 최초 검증 체크!!!!
    
    getCwd = re.sub(r'[\\]', '/', os.getcwd())

    

    # ----------------------------------- 여기부터 잠깐만!!!!!

    exCount = 1

    # 먼저 전체 갯수 가져오기
    while True:
        exCount += 1
        if blogEx.cell(exCount,4).value is None:
            break


    exCount = exCount - 1
    pg.alert(f'{exCount} 번째 부터 시작합니다!')


    startCount = 0
    testWork = False
    newsWork = True # 작업 중간에 빈 창으로 뉴스 읽는 작업 넣어주기! (5분정도)

    for i in range(2):
        
        if i == 1:
            # 엑셀 얼마나 차있는지 보기
            exMaxCount = 1
            while True:
                exMaxCount += 1
                if blogEx.cell(exMaxCount,1).value is None:
                    break

            print(exMaxCount)
            # 쭉 삭제하기!
            exWorkCount = 1
            while True:
                exWorkCount += 1
                blogEx.cell(exWorkCount,4).value = None
                blogWb.save(f"{getCwd}/etc/blog_work.xlsx")
                if exWorkCount >= exMaxCount:
                    break

            exCount = 1
            getDict['loginChkVal'] = True
        
        print(f"i 번째 확인! {i}")
            
        while True:
            print('전체 LOOP 들어옴!!!!')
            if getDict['loginChkVal']:
                newsWork = False
            else:
                newsWork = not newsWork

            startCount += 1

            if newsWork == False:
                exCount += 1
            workBlogNum = blogEx.cell(exCount,1).value

            print(exCount)
            print(workBlogNum)
            if workBlogNum is None:
                for i in range(4):
                    fr = 1550    # range : 37 ~ 32767
                    du = 300     # 1000 ms ==1second
                    sd.Beep(fr, du)
                break

            # 텀 30~40 하니까 아이디가 계속 죽네;;; 10초씩 늘려봄!
            elif startCount != 1 and testWork == False:
                print("1분~1분 10초 대기!!!")
                wait_float(60.0,70.5)

            if newsWork == True:
                print('지금은 newsWork!!!!!!!!!!!!')
                while True:
                    try:
                        res = requests.get(f"{siteLink}/api/v7/res_blog/get_random_useragent").json()
                        print(res)
                        if res['status'] and res['ua_info']:
                            uaContent = res['ua_info']['ua_content']
                            print(uaContent)
                            break
                    except Exception as e:
                        pass
                    wait_float(2.5,3.5)
                while True:
                    if getDict['ipval']:
                        getIp = changeIp()
                        newIp = getIp
                        if oldIp == newIp:
                            continue
                        oldIp = newIp

                    try:
                        options = Options()
                        options.add_argument(f'user-agent={'asdfasdf'}')
                        options.add_experimental_option("excludeSwitches", ["enable-automation"])
                        driver = webdriver.Chrome(options=options)
                        driver.get('https://m.naver.com')
                        driver.set_window_size(600, 600)
                        driver.set_window_position(0,0)
                        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#query")))
                        break
                    except Exception as e:
                        print(e)
                        try:
                            driver.quit()
                        except:
                            pass
                    
                    newsWork = False # 이렇게 해야 False > True 로 변경되면서 다시 뉴스 작업함!!
                    pass
                newsWorkRandomVal = random.randint(3,5)
                newsWorkFunc(driver, newsWorkRandomVal)
                driver.quit()
                continue

            while True:
                print('아이디 얻기 돈댜~~~')
                try:
                    res = requests.get(f"{siteLink}/api/v7/res_blog/get_blog_id_info_m?get_profile={workBlogNum}").json()
                    if res['status'] and res['blog_info']:
                        blogInfo = res['blog_info']
                        uaInfo = res['ua_info']
                        workBlogProfile = blogInfo['n_ch_profile']
                        break
                except Exception as e:
                    print('에러요~~~')
                    print(str(e))
                    pass
                wait_float(2.5,3.5)
            
            print(blogInfo)
            print(uaInfo)
            print(workBlogProfile)
            # 아이피 변경 / 크롬 접속 while~~~~
            while True:
                print('아이피 변경 / 크롬')
                # 아이피 변경 부분!
                if getDict['ipval']:
                    getIp = changeIp()
                    newIp = getIp
                    print(newIp)
                    if oldIp == newIp:
                        continue
                    oldIp = newIp

                # 아이피 변경 부분 끝!!
                    
                try:
                    
                    pcUser = getpass.getuser()
                    options = Options()

                    user_data = f'C:\\Users\\{pcUser}\\AppData\\Local\\Google\\Chrome\\User Data\\default'
                    options.add_argument(f"user-data-dir={user_data}")
                    options.add_argument(f'--profile-directory=Profile {workBlogProfile}')
                    options.add_argument(f'user-agent={uaInfo['ua_content']}')
                    # 이 아래 부분이 (2줄)이 바뀌었음
                    # service = ChromeService(executable_path=ChromeDriverManager().install())
                    # service = Service(ChromeDriverManager().install())
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    driver = webdriver.Chrome(options=options)
                    driver.get('https://m.naver.com')
                    driver.set_window_size(800, 900)
                    driver.set_window_position(0,0)
                    WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#query")))
                    break
                except Exception as e:
                    print(e)
                    driver.quit()
                    pass


            loginStatus = True
            loginStatus = naverLogin_mobile(driver, blogInfo)
            print(loginStatus)

            

            try:
                print('재시도가 나오는 경우가 있음!!!')
                
                wait_float(0.3,0.9)
                retryBtn = driver.find_element(by=By.CSS_SELECTOR, value=".btn_retry")
                retryBtn.click()
                pg.press('F5')
            except:
                pg.press('F5')
                pass

            wait_float(1.7,2.9)




            if loginStatus == False:
                while True:
                    try:
                        res = requests.post(f"{siteLink}/api/v7/res_blog/id_error_chk?", blogInfo).json()
                        print(res)
                        if res['status'] == True:
                            print(res)
                            break
                    except Exception as e:
                        print('에러요~~~') 
                        print(str(e))
                        pass

            try:
                loginChkStatus = True
                exWriteVal = 'OK'
                if getDict['loginChkVal']:
                    testWork = True
                    if loginStatus == False:
                        exWriteVal = 'XX'
                        if getDict['saveChkVal']:
                            for i in range(3):
                                fr = 1550    # range : 37 ~ 32767
                                du = 300     # 1000 ms ==1second
                                sd.Beep(fr, du)
                            pg.alert('보호조치 체크!!')
                            pg.confirm(text='아이디 풀기 성공?', buttons=['OK','NO'])


                    if getDict['directVal'] == 'chk':
                        pg.alert('할거 하기! 이메일 인증이나 뭐나!')
                    elif loginStatus != False:
                        naverIdChkFuncOnlyName(driver,getDict,blogInfo,siteLink,workBlogNum)
                        while True:
                            try:
                                res = requests.post(f"{siteLink}/api/v7/res_blog/id_nomal_chk?", blogInfo).json()
                                print(res)
                                if res['status'] == True:
                                    print(res)
                                    break
                            except Exception as e:
                                print('에러요~~~') 
                                print(str(e))
                                pass
                            wait_float(1.2,1.9)
                        driver.get('https://naver.com')
                        newsWorkFunc(driver, 1)

                    wait_float(2.3,5.5)
                    driver.quit()
                    blogEx.cell(exCount,4).value = exWriteVal
                    blogEx.cell(exCount,5).value = "아이디 체크 완료"
                    blogWb.save(f"{getCwd}/etc/blog_work.xlsx")
                    continue
            except:
                pass

            
            if loginStatus == False:
                blogEx.cell(exCount,4).value = "XX"
                blogWb.save(f"{getCwd}/etc/blog_work.xlsx")
                driver.quit()
                for i in range(3):
                    fr = 1550    # range : 37 ~ 32767
                    du = 300     # 1000 ms ==1second
                    sd.Beep(fr, du)
                continue


            # 글쓰기 부분!!!!!!!!!!!!!!!!!!!!!!!!!

            # 여기에 챗GPT 로 글 가져오는거 하기!!!!

            ex_subject = blogEx.cell(exCount,3).value
            ex_workType = blogEx.cell(exCount,5).value
            ex_linkGroup = blogEx.cell(exCount,7).value

            if ex_subject is not None:
                while True:
            
                    client = OpenAI(
                        api_key = openApiKey,
                    )


                    userInput = f"{ex_subject} 이라는 제목으로 600자 내외 블로그에 작성할 글좀 한줄에 70자 미만으로 줄바꿈 많이 하고 여러 단으로 작성해줘"

                    completion = client.chat.completions.create(
                    model = "gpt-4o",
                    messages = [
                        {"role": "system", "content": userInput},
                    ]
                    )

                    print(completion.choices[0].message.content.strip())

                    content = completion.choices[0].message.content.strip()
                    
                    content = re.sub(r'\b\d+\.', '', content)  # 숫자+점을 제거
                    content = re.sub(r"[^a-zA-Z0-9가-힣\s.?,;:!]", "", content)
                    
                    text_array = content.split("\n\n")
                    print(text_array)
                    print('text_array!!!!!!')


                    resultTemp = insert_img_line_two(text_array)


                    if resultTemp == False:
                        continue
                    else:
                        chkImgLine = has_img_line(resultTemp)
                        if chkImgLine == False:
                            continue
                        else:
                            break
                contentArr = split_elements_by_newline(resultTemp)
                print(contentArr)
                print('contentArr!!!!!!')
                # 제목 삽입
                contentArr.insert(0, ex_subject)
            else:
                file_path = f"./etc/img/{workBlogNum}/content.txt"
                if os.path.isfile(file_path):
                    with open(file_path, "r", encoding="utf-8") as file:
                        lines = file.readlines()
                else:
                    blogEx.cell(exCount,4).value = "OK"
                    blogWb.save(f"{getCwd}/etc/blog_work.xlsx")
                    continue

                if len(lines) == 0:
                    blogEx.cell(exCount,4).value = "OK"
                    blogWb.save(f"{getCwd}/etc/blog_work.xlsx")
                    continue
                contentArr = [line.replace('\n', '') for line in lines]
            
            path = f"{getCwd}/etc/img/{workBlogNum}"
            file_list = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            print(file_list)
            contentArr = replace_img_line_with_files(contentArr,file_list)
            contentArr = remove_plain_img_line(contentArr)
            print(contentArr)


            linkArr = []
            resContentArr = []
            link_index = 0
            # 마지막으로 링크 추가 가져오기!!!


            if ex_workType == 'link' and getDict['linkTwoChkVal']:
                if ex_linkGroup is None:
                    ex_linkGroup = 1
                while True:
                    print('여기서 안되는건가??')
                    try:
                        linkRes = requests.post(f"{siteLink}/api/v7/res_blog/get_link_two", {'link_count' : 1, 'link_group' : ex_linkGroup}).json()
                        print(linkRes)
                        if linkRes['status'] == True and len(linkRes['ran_work_list']) == 2:
                            print(linkRes)
                            break
                    except Exception as e:
                        print(str(e))
                        pass
                getLinkRes = linkRes['ran_work_list']

                if blogEx.cell(exCount,6).value is not None:
                    for item in getLinkRes:
                        link = f'link|{item['tg_keyword']}|{item['tg_link']}'
                        linkArr.append(link)
                else:
                    for item in getLinkRes:
                        link = f'link|{item['tg_link']}'
                        linkArr.append(link)

                for item in contentArr:
                    resContentArr.append(item)
                    if 'img_line' in item and link_index < len(linkArr):
                        resContentArr.append(linkArr[link_index])  # 현재 링크 추가
                        link_index += 1  # 다음 링크로 이동
            elif ex_workType == 'link':
                # 엑셀 작업방식만 사용! 링크 '한개만' 제일 아래 넣기!!
                if ex_linkGroup is None:
                    ex_linkGroup = 1
                while True:
                    print('여기서 안되는건가??')
                    try:
                        linkRes = requests.post(f"{siteLink}/api/v7/res_blog/get_link_one", {'link_group' : ex_linkGroup}).json()
                        print(linkRes)
                        if linkRes['status'] == True:
                            print(linkRes)
                            getLinkObj = linkRes['work_link']
                            break
                    except Exception as e:
                        print(str(e))
                        pass

                resContentArr = contentArr

                resContentArr.append("enter")
                resContentArr.append(f'link|{getLinkObj['tg_keyword']}|{getLinkObj['tg_link']}')
            else:
                # 이건 링크가 없을때!!
                resContentArr = contentArr
            

            print(resContentArr)
            print('글쓰기 시작 해야지?!?!?!?!?!?!?!??!!')

            while True:
                writeRes = writeBlog(driver,workBlogNum,resContentArr)
                if writeRes['status']:
                    break
            

            # 글 작성 끄읕~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~!!!!


            print('글 작성은 끝났니?!?!??!')

            

            # 블로그 메인으로 이동
            while True:
                driver.get('https://naver.com')
                try:
                    wait_float(1.2,1.9)
                    mainBtnList = driver.find_elements(by=By.CSS_SELECTOR, value=".shs_text")
                    for btn in mainBtnList:
                        if '블로그' in btn.text:
                            btn.click()
                except:
                    pass

                try:
                    wait_float(1.2,1.9)
                    # 에디터 변경 확인 modal
                    editorInfoModalCloseBtn = driver.find_element(by=By.CSS_SELECTOR, value="._da-nomoreshow")
                    editorInfoModalCloseBtn.click()
                except Exception as e:
                    pass

                try:
                    wait_float(1.2,1.9)
                    blogMainChk = driver.find_elements(by=By.CSS_SELECTOR, value=".lottie_logo__CzKBx")
                    if len(blogMainChk) > 0:
                        break
                except:
                    pass

                

                
                # try:
                #     wait_float(1.2,1.9)
                #     goToBlogMain = driver.find_element(by=By.CSS_SELECTOR, value=".Nservice_item")
                #     goToBlogMain.click()
                # except:
                #     pass

                

            blogListNum = 0
            try:
                # 이웃블로그 갯수 찾기
                blogList = driver.find_elements(by=By.CSS_SELECTOR, value=".title__mA4zy")
                blogListNum = len(blogList)
            except:
                pass

            if blogListNum > 5:
                # 이웃블로그 있으면 돌기!
                random_value = random.randint(5, 7)
                for i in range(random_value):
                    print('이웃 블로그 돌기!!')
                    while True:
                        try:
                            wait_float(1.2,1.9)
                            # 에디터 변경 확인 modal
                            editorInfoModalCloseBtn = driver.find_element(by=By.CSS_SELECTOR, value="._da-nomoreshow")
                            editorInfoModalCloseBtn.click()
                        except Exception as e:
                            pass
                        try:
                            wait_float(1.2,1.9)
                            blogList = driver.find_elements(by=By.CSS_SELECTOR, value=".title__mA4zy")
                            if len(blogList) > 0:
                                randomBlogNum = random.randint(0, len(blogList))
                                blogList[randomBlogNum].click()
                                break
                        except:
                            pass
                    scrollRanVal = random.randint(5, 10)
                    for k in range(scrollRanVal):
                        scrollRangeVal = random.randint(300,500)
                        pg.moveTo(200,500)
                        pg.scroll(-scrollRangeVal)
                        wait_float(1.5,2.5)
                    driver.back()
            else:
                # 없으면 새 블로그들 찾기
                errCount = 0
                while True:
                    print('이웃 말고 다른 블로그 찾기!')
                    errCount += 1
                    if errCount > 10:
                        pg.press('F5')
                        wait_float(5.5,7.5)

                    try:
                        wait_float(1.2,1.9)
                        # 에디터 변경 확인 modal
                        editorInfoModalCloseBtn = driver.find_element(by=By.CSS_SELECTOR, value="._da-nomoreshow")
                        editorInfoModalCloseBtn.click()
                    except Exception as e:
                        pass
                    try:
                        blogMenuList = driver.find_elements(by=By.CSS_SELECTOR, value=".item__mSPvI")
                        for blogMenu in blogMenuList:
                            if '추천' in blogMenu.text:
                                blogMenu.click()
                                break
                    except:
                        pass

                    try:
                        blogList = driver.find_elements(by=By.CSS_SELECTOR, value=".title__Hj5DO")
                        if len(blogList) > 5:
                            break
                    except:
                        pass

                    
                random_value = random.randint(5, 7)
                for i in range(random_value):
                    print('이웃 말고 다른 블로그 찾기!')
                    errCount = 0
                    while True:
                        errCount += 1
                        if errCount > 10:
                            pg.press('F5')
                            wait_float(5.5,7.5)
                        try:
                            wait_float(1.2,1.9)
                            blogList = driver.find_elements(by=By.CSS_SELECTOR, value=".title__Hj5DO")
                            if len(blogList) > 0:
                                randomBlogNum = random.randint(0, len(blogList))
                                blogList[randomBlogNum].click()
                                break
                        except:
                            pass
                    scrollRanVal = random.randint(5, 10)
                    for k in range(scrollRanVal):
                        scrollRangeVal = random.randint(300,500)
                        pg.moveTo(200,500)
                        pg.scroll(-scrollRangeVal)
                        wait_float(1.5,2.5)
                    driver.back()
                    


            while True:
                print('다 완료!!')
                wait_float(1.5,2.5)
                resBlogId = ""
                getBlogId = writeRes['url'].split('/')[3]
                if getBlogId != blogInfo['n_id']:
                    resBlogId = getBlogId
                
                try:
                    res = requests.get(f"{siteLink}/api/v7/res_blog/memo_update?get_nidx={workBlogNum}&blog_id={resBlogId}").json()
                    print(res)
                    if res['status']:
                        print(res)
                        break
                except Exception as e:
                    print(str(e))
                    pass
            
            for i in range(2):
                fr = 1550    # range : 37 ~ 32767
                du = 300     # 1000 ms ==1second
                sd.Beep(fr, du)
            blogEx.cell(exCount,4).value = "OK"
            blogWb.save(f"{getCwd}/etc/blog_work.xlsx")

            driver.quit()
        
    pg.alert('종료합니다!!')
    sys.exit(0)





# ***************************************************************


