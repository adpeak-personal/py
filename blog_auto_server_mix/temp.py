def blogCafeWork(getDict):
    
    
    cafeIdEx = load_workbook('./etc/cafeid.xlsx')
    cafeIdSheet = cafeIdEx.active
    
    getCwd = re.sub(r'[\\]', '/', os.getcwd())
    pg.alert('카페 작업 시작!')
    preIp = ''
    
    
    cafeWorkCount = 1
    
    workOutArr = []
    articleCount = 0
    pageCount = 0
    while True:
        cafeWorkCount += 1
        
        if cafeIdSheet.cell(cafeWorkCount, 2).value is None:
            pg.alert('종료합니다!')
            sys.exit(1)
        
        try:
            try:
                with open(f'./etc/subject_list.txt', 'rt', encoding='UTF8') as f:
                    subjectLines = f.readlines()
            except:
                with open(f'./etc/subject_list.txt', 'r') as f:
                    subjectLines = f.readlines()
        except:
            pass
        
        while True:
            sjRanVal = random.randrange(0,len(subjectLines))
            if sjRanVal in workOutArr:
                continue
            else:
                break
        workOutArr.append(sjRanVal)
        
        
        
        while True:
            if getDict['ipval'] == 1:
                while True:
                    print('아이피 변경 작업 시작!!')
                    getIP = changeIp()
                    print(getIP)
                    print(preIp)

                    if preIp == getIP:
                        continue
                    else:
                        preIp = getIP
                        break
                    
            
            try:
                pg.alert('여기는 오니?!?!')
                options = Options()
                user_data = 'C:\\Users\\pcy\\AppData\\Local\\Google\\Chrome\\User Data\\default'
                service = Service(ChromeDriverManager().install())
                options.add_argument(f"user-data-dir={user_data}")
                # if getDict['profileVal'] == 1:
                #     
                options.add_argument(f'--profile-directory={cafeIdSheet.cell(cafeWorkCount, 1).value}')

                driver = webdriver.Chrome(service=service, chrome_options=options)
                driver.set_page_load_timeout(7)

                driver.get('https://www.naver.com')
                driver.set_page_load_timeout(30)
                driver.set_window_size(1100, 800)
                driver.set_window_position(0,0)
                pg.alert('빡치게좀 하지마')
                break
            except Exception as e:
                print(e)
                pass

        
        
        loginBtn = searchElement('.sc_login',driver)
        loginBtn[0].click()
        searchElement('#id',driver)
        focus_window('로그인')
        wait_float(0.3,0.9)
        while True:
            
            pg.click(250,500)
            inputId = driver.find_element(by=By.CSS_SELECTOR, value="#id")
            inputId.click()
            wait_float(0.3,0.9)
            cb.copy(cafeIdSheet.cell(cafeWorkCount, 2).value)
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
            cb.copy(cafeIdSheet.cell(cafeWorkCount, 3).value)
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
        
        
        
        # 카페 진입 ~ 글쓰기 버튼 클릭까지!
        while True:
            try:
                wait_float(0.7,1.5)
                driver.switch_to.default_content()
                cafeMainChk = driver.find_element(by=By.CSS_SELECTOR, value="#cafe-body-skin")
            except:
                driver.get('https://cafe.naver.com/sens3')
                pass
            
            try:
                wait_float(0.7,1.5)
                workMenu = driver.find_element(by=By.CSS_SELECTOR, value="#menuLink226")
                boldChk = workMenu.get_attribute('class')
                if boldChk != 'gm-tcol-c b':
                    workMenu.click()
            except:
                pass
            
            try:
                wait_float(0.7,1.5)
                
                driver.switch_to.frame('cafe_main')
                writeBtn = driver.find_element(by=By.CSS_SELECTOR, value="#writeFormBtn")
                writeBtn.click()
            except:
                pass
            if len(driver.window_handles) == 2:
                break
        while True:
            focus_window('Chrome')
            try:
                wait_float(0.7,1.5)
                driver.switch_to.window(driver.window_handles[1])
                driver.switch_to.default_content()
                subjectArea = driver.find_element(by=By.CSS_SELECTOR, value=".FlexableTextArea")
                subjectArea.click()
                cb.copy(subjectLines[sjRanVal])
                pg.hotkey('ctrl', 'v')
                
                wait_float(2.5,3.5)
                
                # contentArea = driver.find_element(by=By.CSS_SELECTOR, value=".se-content")
                # contentArea.click()
                contentLineList = driver.find_elements(by=By.CSS_SELECTOR, value=".se-text-paragraph")
                contentLineList[2].click()
                cb.copy(cafeIdSheet.cell(cafeWorkCount, 4).value)
                pg.hotkey('ctrl', 'v')
                
                wait_float(4.5,6.2)
                
                successBtn = driver.find_element(by=By.CSS_SELECTOR, value=".BaseButton.BaseButton--skinGreen")
                successBtn.click()
                
                wait_float(4.5,6.2)
                driver.close()
                
                break
            except:
                pass
        
        
        pg.alert('글 다 썼다고 치고!!!')
        
        i = 0
        # 댓글 시작!! 
        while i < 5:
            i += 1
            articleCount += 1
            
            
            while True:
                print("메뉴 클릭해서 초기화!!")
                try:
                    driver.switch_to.window(driver.window_handles[0])
                    driver.switch_to.default_content()
                    wait_float(0.7,1.5)
                    driver.switch_to.default_content()
                    workMenu = driver.find_element(by=By.CSS_SELECTOR, value="#menuLink226")
                    workMenu.click()
                except:
                    pass
                
                try:
                    wait_float(1.9,2.5)
                    driver.switch_to.frame('cafe_main')
                    boardList = driver.find_element(by=By.CSS_SELECTOR, value=".article-board.m-tcol-c")
                    break
                except:
                    pass
            
            if pageCount != 0:
                pageTagList = driver.find_elements(by=By.CSS_SELECTOR, value=".prev-next a")
                pageTagList[pageCount].click()

            while True:
                print('게시판(글 목록) 찾기 > 순서 맞춰 게시글 찾기 > 게시글 들어갔는지 체크')
                try:
                    wait_float(0.7,1.5)
                    boardList = driver.find_elements(by=By.CSS_SELECTOR, value=".article-board.m-tcol-c")
                    if not boardList:
                        continue
                except:
                    pass
                
                try:
                    wait_float(0.3,0.9)
                    articleList = boardList[-1].find_elements(by=By.CSS_SELECTOR, value=".article")
                    if articleCount > len(articleList):
                        pageCount += 1
                        pageTagList = driver.find_elements(by=By.CSS_SELECTOR, value=".prev-next a")
                        pageTagList[pageCount].click()
                        articleCount = 0
                    else:
                        articleList[articleCount].click()
                except:
                    pass
                
                try:
                    wait_float(0.3,0.9)
                    inArticleChk = driver.find_element(by=By.CSS_SELECTOR, value=".ArticleContentBox")
                    if inArticleChk:
                        break
                except:
                    pass
            
            linkStatus = ''
            while True:
                print('게시글 내에서 링크 찾아서 클릭!')
                wait_float(0.7,1.5)
                driver.switch_to.default_content()
                driver.switch_to.frame('cafe_main')
                
                if linkStatus == '':
                    try:
                        wait_float(0.7,1.5)
                        linkChkEle = driver.find_element(by=By.CSS_SELECTOR, value=".se-oglink-info")
                        linkChk = linkChkEle.get_attribute('href')
                        if 'm.' in linkChk:
                            linkStatus = 'bad'
                            break
                        
                        linkStatus = 'on'
                        linkChkEle.click()
                        
                    except Exception as e:
                        pass
                
                
                if linkStatus == '':
                    try:
                        wait_float(0.7,1.5)
                        linkChkEle = driver.find_element(by=By.CSS_SELECTOR, value=".se-link")
                        linkChk = linkChkEle.get_attribute('href')
                        if 'm.' in linkChk:
                            linkStatus = 'bad'
                            break
                        linkStatus = 'on'
                        linkChkEle.click()
                    except Exception as e:
                        print(e)
                        pass
                
                pg.alert(len(driver.window_handles))
                
                if len(driver.window_handles) >= 2:
                    break
                
            if linkStatus == 'bad':
                i = i - 1
                continue
            
            while True:
                try:
                    driver.switch_to.window(driver.window_handles[1])
                    wait_float(0.3,0.9)
                    driver.switch_to.default_content()
                    wait_float(0.3,0.9)
                    driver.switch_to.frame('mainFrame')
                    wait_float(0.3,0.9)
                    break
                except:
                    pass
            
            
            # 여기서 블로그 말고 프롤로그면 블로그 클릭하게 하기
            while True:
                print("프롤로그면 블로그 클릭!")
                try:
                    wait_float(0.7,1.2)
                    
                    
                    blogMenuChk = driver.find_elements(by=By.CSS_SELECTOR, value="#blog-menu .menu1 li a")
                    if(len(blogMenuChk) > 1):
                        blogMenuChk[1].click()
                except:
                    pass
                
                try:
                    wait_float(0.7,1.2)
                    postListOpenBtn = driver.find_element(by=By.CSS_SELECTOR, value="#toplistSpanBlind")
                    break
                except:
                    pass
                
            while True:
                try:
                    wait_float(0.7,1.2)
                    allView = driver.find_element(by=By.CSS_SELECTOR, value="#category0")
                    allView.click()
                    break
                except:
                    pass
                
                try:
                    wait_float(0.7,1.2)
                    categoryToggle = driver.find_element(by=By.CSS_SELECTOR, value=".cm-icol._viewMore")
                    categoryToggle.click()
                except:
                    pass

            while True:
                print("목록 열기 클릭!!")
                try:
                    wait_float(0.7,1.2)
                    postListOpenBtn = driver.find_element(by=By.CSS_SELECTOR, value="#toplistSpanBlind")
                    if postListOpenBtn.text == '목록닫기':
                        break
                    else:
                        postListOpenBtn.click()
                except:
                    pass
                
            
            while True:
                print("가장 최근 글 클릭!")
                try:
                    wait_float(0.7,1.2)
                    postListWrap = driver.find_element(by=By.CSS_SELECTOR, value=".wrap_blog2_categorylist")
                    workPost = postListWrap.find_element(by=By.CSS_SELECTOR, value=".ell2.pcol2")
                    workPost.click()
                except:
                    pass
                
                try:
                    wait_float(0.7,1.2)
                    gongamBtnWrap = driver.find_element(by=By.CSS_SELECTOR, value=".wrap_postcomment")
                    gongamBtnChk = gongamBtnWrap.find_elements(by=By.CSS_SELECTOR, value="div")
                except:
                    pass
                
                if gongamBtnChk:
                    if len(gongamBtnChk) < 5:
                        linkStatus = 'bad'
                    break
                
            if linkStatus == 'bad':
                driver.close()
                i = i - 1
                continue
            
            
            pg.alert('공감 클릭 부분!!!')

            ggStop = ''
            while True:
                gongamBtn = driver.find_elements('.u_likeit_list_module._reactionModule', driver)
                if gongamBtn:
                    for btn in gongamBtn:
                        try:
                            btn.click()
                            ggStop = 'on'
                            break
                        except:
                            pass
                    if ggStop == 'on':
                        break
                
            # while True:
            #     print("공감 버튼 클릭!")
            #     try:
            #         gongamBtnWrap = driver.find_element(by=By.CSS_SELECTOR, value='.u_likeit_list_btn._button.pcol2')
            #         getGonggamStatus = gongamBtnWrap.get_attribute('aria-pressed')
            #         print(getGonggamStatus)
            #         wait_float(0.3,0.9)
            #         if getGonggamStatus == 'false':
            #             gongamBtn = gongamBtnWrap.find_element(by=By.CSS_SELECTOR, value='.u_ico._icon')
            #             wait_float(0.3,0.9)
            #             driver.execute_script("arguments[0].scrollIntoView();", gongamBtn)
            #             wait_float(0.3,0.9)
            #             pg.scroll(-500)
            #             gongamBtn.click()
            #         break
            #     except:
            #         pass
            
            pg.alert('공감 클릭 확인!!')
            
            driver.close()
            
            

            try:
                with open(f'./etc/reply_list.txt', 'rt', encoding='UTF8') as f:
                    replyLines = f.readlines()
            except:
                with open(f'./etc/reply_list.txt', 'r') as f:
                    replyLines = f.readlines()
            
            reRanVal = random.randrange(0,len(replyLines))
            replyContent = replyLines[reRanVal]
            
            while True:
                print('댓글 남기기!!')
                try:
                    driver.switch_to.window(driver.window_handles[0])
                    
                    wait_float(0.7,1.5)
                    driver.switch_to.default_content()
                    driver.switch_to.frame('cafe_main')
                    wait_float(0.7,1.5)
                    commentArea = driver.find_element(by=By.CSS_SELECTOR, value='.comment_inbox_text')
                    commentArea.click()
                    
                    cb.copy(replyContent)
                    pg.hotkey('ctrl', 'v')
                    wait_float(1.5,2.2)
                    cb.copy(cafeIdSheet.cell(cafeWorkCount, 4).value)
                    pg.hotkey('ctrl', 'v')
                    wait_float(1.5,2.2)
                    
                    commentSuccessBtn = driver.find_element(by=By.CSS_SELECTOR, value='.btn_register.is_active')
                    commentSuccessBtn.click()
                    break
                except:
                    pass
            
            wait_float(3.5,4.5)
            pg.alert('되돌기 대기!!!')
            
                
                
        
        
        pg.alert('종료합니다!')
                
                
            


# 이웃 순방을 할까~~ 말까~~~
def visitNeighborWork(driver):

    driver.switch_to.default_content()
    neighborEx = load_workbook('./etc/neighbor_list.xlsx')
    neighborSheet = neighborEx.active

    neighborAllCount = 0
    while True:
        neighborAllCount += 1
        if neighborSheet.cell(neighborAllCount, 1).value is None:
            break
    
    ranBlogLink = random.sample(range(1,neighborAllCount),10)

    for ranVal in ranBlogLink:
        getLink = neighborSheet.cell(ranVal, 1).value
        driver.get(getLink)

        no_posting = ''
        while True:
            print("프롤로그면 블로그 클릭!")
            try:
                wait_float(0.7,1.2)
                driver.switch_to.default_content()
                driver.switch_to.frame('mainFrame')
                blogMenuChk = driver.find_elements(by=By.CSS_SELECTOR, value="#blog-menu .menu1 li a")
                for blogMenu in blogMenuChk:
                    if blogMenu.text == '블로그':
                        blogMenu.click()
                # if(len(blogMenuChk) > 1):
                #     blogMenuChk[1].click()
            except:
                pass
            
            try:
                wait_float(0.7,1.2)
                postListOpenBtn = driver.find_element(by=By.CSS_SELECTOR, value="#toplistSpanBlind")
                break
            except:
                pass
            
            try:
                wait_float(0.7,1.2)
                postListOpenBtn = driver.find_element(by=By.CSS_SELECTOR, value=".new_blog_inner2")
                no_posting == 'on'
                break
            except:
                pass
        
        # 가장 먼저 포스팅 갯수 찾기! 포스팅 갯수 10개 미만이면 패스~~
        noWork = ''
        while True:
            print("포스팅 갯수 찾기!")
            wait_float(0.7,1.2)
            try:
                
                postingCountEle = driver.find_element(by=By.CSS_SELECTOR, value=".num.cm-col1")
                postingCount = re.sub(r'[^0-9]', '', postingCountEle.text)
                print(f"작업중 블로그의 포스팅 갯수는?! {int(postingCount)}")
                
                if int(postingCount) < 10:
                    noWork = 'on'
                    break
            except:
                pass

            try:
                allview = driver.find_element(by=By.CSS_SELECTOR, value=".cm-head.cm_cur._viewMore")
                allview.click()
                if int(postingCount) > 10:
                    break
            except:
                pass
                
        
        if noWork == 'on':
            neighborSheet.cell(ranVal, 2).value = '비정상 블로그'
            neighborEx.save('./etc/neighbor_list.xlsx')
            continue
        
        while True:
            print("목록 열기 클릭!!")
            try:
                postListOpenBtn = driver.find_element(by=By.CSS_SELECTOR, value="#toplistSpanBlind")
                if postListOpenBtn.text == '목록닫기':
                    break
                else:
                    postListOpenBtn.click()
            except:
                pass
        

        while True:
            print("가장 최근 글 클릭!")
            try:
                wait_float(0.7,1.2)
                postListWrap = driver.find_element(by=By.CSS_SELECTOR, value=".wrap_blog2_categorylist")
                if postListWrap:
                    print("postListWrap 있음")
                workPost = postListWrap.find_element(by=By.CSS_SELECTOR, value=".ell2.pcol2")
                print(workPost.text)
                workPost.click()
            except:
                pass
            
            try:
                wait_float(1.5,2.2)
                subjectEle = driver.find_element(by=By.CSS_SELECTOR, value=".se-title-text")
                if subjectEle:
                    break
            except:
                pass
            
            try:
                wait_float(1.2,1.9)
                subjectEle = driver.find_element(by=By.CSS_SELECTOR, value=".se_textView")
                if subjectEle:
                    break
            except:
                pass

            ranRange = random.randrange(1, 4)
            for i in range(ranRange):
                wait_float(1.2,1.9)
                pg.scroll(-500)
        
        
        noSearchCount = 0
        replyAction = True
        while True:
            noSearchCount += 1
            print(f"공감 에러 count는? : {noSearchCount}")
            if noSearchCount > 4:
                replyAction = False
                break
                
            print('공감 클릭 돌아돌아')
            try:
                wait_float(1.2,1.9)
                gongamSuccess = driver.find_element(by=By.CSS_SELECTOR, value=".u_likeit_list_btn._button.pcol2.on")
                print('공감 성공!!!')
                if gongamSuccess:
                    break
            except:
                pass

            try:
                wait_float(1.2,1.9)
                gongamBtn = driver.find_element(by=By.CSS_SELECTOR, value=".u_ico._icon.pcol3")
                gongamBtn.click()
            except:
                pass
            
        if replyAction:
            replyActionRanVal = random.randrange(0,3)
            if replyActionRanVal == 0:
                continue
        else:
            continue
        
        
        
        replyErrCount = 0
        replyStatus = ''
        while True:
            replyErrCount += 1
            if replyErrCount > 4:
                replyStatus = "no_reply"
                break
            print(f"에러 카운트는? {replyErrCount}")
            
            print('댓글열기~~~ 돌아돌아')
            try:
                wait_float(1.2,1.9)
                commentToggleBtn = driver.find_element(by=By.CSS_SELECTOR, value=".area_comment.pcol3")
                commentToggleBtn.click()
            except:
                pass

            try:
                wait_float(1.2,1.9)
                commentToggleBtn = driver.find_element(by=By.CSS_SELECTOR, value=".area_comment.pcol2")
                commentToggleBtn.click()
            except:
                pass

            try:
                wait_float(1.2,1.9)
                commentTextArea = driver.find_element(by=By.CSS_SELECTOR, value=".u_cbox_guide")
                commentTextArea.click()
                break
            except:
                pass
        
        if replyStatus == "no_reply":
            continue    
            
        try:
            with open(f'./etc/blog_reply_list.txt', 'rt', encoding='UTF8') as f:
                getLines = f.readlines()
        except:
            with open(f'./etc/blog_reply_list.txt', 'r') as f:
                getLines = f.readlines()
                
        getReplyRanVal = random.randrange(0,len(getLines))
        
        keyboard.write(text=getLines[getReplyRanVal], delay=0.05)
        
        while True:
            try:
                wait_float(1.2,1.9)
                replySuccessBtn = driver.find_element(by=By.CSS_SELECTOR, value=".u_cbox_btn_upload")
                replySuccessBtn.click()
                break
            except:
                pass
        
        neighborAlready = False
        while True:
            try:
                wait_float(1.2,1.9)
                addNeighborBtn = driver.find_element(by=By.CSS_SELECTOR, value=".btn_add_nb._addBuddyPop._rosRestrictAll")
                if addNeighborBtn.text == '이웃추가':
                    neighborAlready = True
                    break
                else:
                    addNeighborBtn.click()
            except:
                pass
            
            if len(driver.window_handles) > 1:
                break
        
        if neighborAlready:
            continue
        
        while True:
            driver.switch_to.window(driver.window_handles[1])
            try:
                wait_float(1.2,1.9)
                btnbtn1 = driver.find_element(by=By.CSS_SELECTOR, value=".button_next._buddyAddNext")
                btnbtn1.click()
            except:
                pass
            
            try:
                wait_float(1.2,1.9)
                btnbtn1 = driver.find_element(by=By.CSS_SELECTOR, value=".button_next._addBuddy")
                btnbtn1.click()
            except:
                pass
            
            try:
                wait_float(1.2,1.9)
                btnbtn1 = driver.find_element(by=By.CSS_SELECTOR, value=".area_button .button_close")
                btnbtn1.click()
            except:
                pass
            
            if len(driver.window_handles) == 1:
                driver.switch_to.window(driver.window_handles[0])
                break