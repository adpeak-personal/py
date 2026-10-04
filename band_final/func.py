import random
import threading
import time
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path
# from typing import Optional
# from pyparsing import And
import requests
from requests import get
import shutil
# from bs4 import BeautifulSoup as bs
import json
import re
import pyautogui as pg
import pyperclip
import pygetwindow as gw
import clipboard as cb
from openpyxl import load_workbook
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import WebDriverException

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
# import chromedriver_autoinstaller
# from ppadb.client import Client as AdbClient
import keyboard
from tkinter import *
from tkinter import ttk
import winsound as ws
import glob
import asyncio
import winsound as sd
import shutil
import getpass
import urllib.request
import zipfile
from pywinauto.application import Application
from pywinauto import Desktop
from pywinauto.timings import TimeoutError as PywinautoTimeout
import time, os



def bandWritePost(driver):
    # 이미지 업로드 하기!!!!!!


    # 1. 글쓰기 버튼 클릭 / 2. 글쓰기 모달 창 확인 / 3. 이미지 업로드 버튼 클릭 / 4. 이미지 업로드 / 5. 이미지 업로드 확인 까지~~
    errCount = 0
    while True:


        errCount += 1
        if errCount > 10:
            pg.press('F5')
            wait_float(1.5,2.5)
            errCount = 0
        
        print('글쓰기 돈다잉!!!!')

        try:
            wait_float(0.5,1.2)
            postWriteBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnPostWrite")
            postWriteBtn.click()
        except Exception as e:
            print('글쓰기 버튼 클릭 에러!!!')
            print(str(e))
            pass

        try:
            wait_float(0.5,1.2)
            postWriteModal = driver.find_elements(by=By.CSS_SELECTOR, value=".lyWrap._lyWrap")
            if len(postWriteModal) == 0:
                continue
        except Exception as e:
            print('모달 창 확인 에러!!')
            pass


        try:
            wait_float(0.5,1.2)
            imgUploadBtns = driver.find_elements(by=By.CSS_SELECTOR, value="._btnAttachPhoto")
            print(f"imgUploadBtns 갯수 : {len(imgUploadBtns)}")
            for imgUploadBtn in imgUploadBtns:
                imgUploadBtn.click()
        except Exception as e:
            print(str(e))
            print('파일 업로드 버튼 클릭 에러!!')
            pass

        try:
            wait_float(0.3,0.9)
            fileInputWinBool = focus_window('열기')
            if fileInputWinBool == False:
                continue

            print("파일 선택 창이 열려 있습니다.")


            nowPath = os.getcwd()

            for i in range(5):
                fileInputWinBool = focus_window('열기')
                if fileInputWinBool == False:
                    break
                content_image_path = nowPath + f"\etc\content\image"

                cb.copy(content_image_path)
                wait_float(0.5,1.2)
                pg.hotkey('ctrl', 'v')
                wait_float(0.5, 1.2)
                pg.press('enter')
                wait_float(1.5, 2.5)

            pg.press('enter')
            wait_float(1.2,1.9)

        except Exception as e:
            print(str(e))
            pass


        errcount = 0
        imgErrStatus = False
        while True:
            errcount += 1
            if errcount > 10:
                imgErrStatus = True
                errcount = 0
                break
            try:
                wait_float(1.2,1.5)
                focus_window('Chrome')
                imgSubmitBtn = driver.find_element(by=By.CSS_SELECTOR, value=".uButton.-confirm._submitBtn")
                imgSubmitBtn.click()
                break
            except Exception as e:
                print('파일 업로드 완료 버튼 클릭 에러!!')
                continue
        
        if imgErrStatus:
            while True:
                try:
                    wait_float(0.3,0.9)
                    focus_window('열기')
                    wait_float(0.3,0.9)
                    pg.press('esc')
                    wait_float(0.3,0.9)
                    focus_window('Chrome')
                    wait_float(0.3,0.9)
                    pg.press('esc')
                    wait_float(0.3,0.9)
                except:
                    pass

                try:
                    postWriteModal = driver.find_elements(by=By.CSS_SELECTOR, value=".lyWrap._lyWrap")
                    if len(postWriteModal) == 0:
                        pg.press('F5')
                        break
                except:
                    pass
            continue
        else:
            break

    wait_float(1.2, 1.9)
    
    while True:
        content = ""
        while True:

            try:
                with open(f'./etc/content/content.txt', 'rt', encoding='UTF8') as f:
                    content = f.read()
            except:
                pass

            try:
                with open(f'./etc/content/content.txt', 'r') as f:
                    content = f.read()
            except:
                pass

            if content == '':
                continue
            else:
                break

        try:
            focus_window('Chrome')
            pg.press('enter')
            pg.press('enter')
            pg.press('enter')
            cb.copy(content)
            wait_float(0.5,1.2)
            pg.hotkey('ctrl', 'v')
            wait_float(0.5, 1.2)
            pg.press('enter')
            wait_float(1.2, 1.5)
        except:
            pass

        try:
            wait_float(0.5,1.2)
            contentChk = driver.find_elements(by=By.CSS_SELECTOR, value=".cke_widget_wrapper.cke_widget_block")
            print(f"contentChk 갯수 : {len(contentChk)}")
            if len(contentChk) == 0:
                pg.press('F5')
                wait_float(1.5,2.5)
                continue
            else:
                break
        except:
            pass

    

    while True:
        try:
            wait_float(1.2,1.9)
            submitBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnSubmitPost")
            submitBtn.click()
        except:
            pass

        try:
            wait_float(1.2,1.9)
            boardSelect = driver.find_elements(by=By.CSS_SELECTOR, value="#uCheck")
            if len(boardSelect) > 0:
                ranNum = random.randrange(0, len(boardSelect))
                boardSelect[ranNum].click()
        except:
            pass

        try:
            wait_float(2.5,3.5)
            btnConfirm = driver.find_element(by=By.CSS_SELECTOR, value=".uButton.-confirm._btnConfirm")
            btnConfirm.click()
            break
        except:
            pass


def deleteLatestPost(driver):
    # 멤버 _lnbMenus[4] > 내 정보 _btnSetting > 내 게시글 _btnGotoSearchMemberContent
    # 멤버 > 내 게시글 > 오래된순 정렬까지!!
    while True:
        focus_window('Chrome')
        try:
            wait_float(0.8,1.5)
            memberBtn = driver.find_elements(by=By.CSS_SELECTOR, value=".lnbTopMenuItemLink")
            memberBtn[4].click()
        except Exception as e:
            print(str(e))
            pass

        try:
            wait_float(0.8,1.5)
            settingBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnSetting")
            settingBtn.click()
        except Exception as e:
            print(str(e))
            pass

        try:
            wait_float(0.8,1.5)
            myPostListBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnGotoSearchMemberContent")
            myPostListBtn.click()
        except Exception as e:
            print(str(e))
            pass

        try:
            wait_float(0.8,1.5)
            sortSelectBtn = driver.find_element(by=By.CSS_SELECTOR, value=".buttonSorting._btnSort")
            sortSelectBtn.click()
        except Exception as e:
            print(str(e))
            pass

        try:
            wait_float(1.2,1.9)
            selectList = driver.find_elements(by=By.CSS_SELECTOR, value="._optionMenuLink")
            print(selectList)
            selectList[1].click()
            break
        except Exception as e:
            print(str(e))
            pass

    # 게시글 삭제 루프!! 최신 1개 남기고 다 지우기!!
    while True:
        focus_window('Chrome')
        try:
            wait_float(0.8,1.5)
            myPostList = driver.find_elements(by=By.CSS_SELECTOR, value=".postSet._btnPostMore")
            if len(myPostList) <= 1:
                break
            else:
                myPostList[0].click()
        except Exception as e:
            print('메뉴 버튼 wrap 오픈 에러')
            print(str(e))
            pass

        try:
            wait_float(0.8,1.5)
            myPostMenu = driver.find_element(by=By.CSS_SELECTOR, value=".lyMenu._postMoreMenu")
            deleteBtns = myPostMenu.find_elements(by=By.CSS_SELECTOR, value="._postMoreMenuUl li")
            for deleteBtn in deleteBtns:
                print(deleteBtn.text)
                if deleteBtn.text == "삭제하기":
                    deleteBtn.click()
        except Exception as e:
            print('메뉴 버튼 클릭 에러')
            print(str(e))
            pass

        try:
            wait_float(0.8,1.5)
            confirmBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnConfirm")
            confirmBtn.click()
        except Exception as e:
            print('삭제 확인 버튼 클릭 에러')
            print(str(e))
            pass


def latestPostChk(driver):
    latestPostChkBool = False # 가장 최신글이 내 글인지 체크하는 변수
    notRegistBool = False
    while True:
        focus_window('Chrome')
        try:
            wait_float(0.8,1.5)
            joinChk = driver.find_elements(by=By.CSS_SELECTOR, value="._btnJoinBand")
            if len(joinChk) > 0:
                notRegistBool = True
                break
        except Exception as e:
            print(str(e))
            continue

        try:
            wait_float(0.8,1.5)
            latestChk = driver.find_element(by=By.CSS_SELECTOR, value=".postSet._btnPostMore")
            latestChk.click()
        except Exception as e:
            print(str(e))
            continue

        try:
            wait_float(0.8,1.5)
            firstMenu = driver.find_element(by=By.CSS_SELECTOR, value=".lyMenu._postMoreMenu")
            menuList = firstMenu.find_elements(by=By.CSS_SELECTOR, value="._postMoreMenuUl li")

            try:
                if '삭제하기' in menuList[4].text:
                    latestPostChkBool = True
            except:
                pass

            try:
                if '삭제하기' in menuList[5].text:
                    latestPostChkBool = True
            except:
                pass

            break
        except Exception as e:
            print(str(e))
            continue

    # 가입을 했지만 가입이 안되어 있을 경우 continue
    if notRegistBool == True or latestPostChkBool == True:
        return False


def joinband(driver, profile, bandStatus):

    profileSuccessStatus = False
    # 밴드 가입 메인!! 가입하기 버튼이 사라지면 탈출!!
    errStatus = False
    while True:

        # 글쓰기 버튼이 있으면 이미 가입된 밴드!!
        try:
            wait_float(0.5, 1.2)
            writeBtn = driver.find_elements(by=By.CSS_SELECTOR, value="._btnPostWrite")
            print(len(writeBtn))
            if len(writeBtn) > 0:
                bandStatus['status'] = True
                return bandStatus
        except:
            pass

                # 글쓰기 버튼이 있으면 이미 가입된 밴드!!
        try:
            wait_float(0.5, 1.2)
            writeBtn = driver.find_elements(by=By.CSS_SELECTOR, value="._btnPostWrite")
            print(len(writeBtn))
            if len(writeBtn) > 0:
                bandStatus['status'] = True
                return bandStatus
        except:
            pass


        # 가입 버튼 클릭 > 가입 모달창 뜨면 break
        while True:
            print('가입 버튼 클릭 gogo')

            try:
                wait_float(0.5, 1.0)
                joinBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnJoinBand")
                if '가입신청' in joinBtn.text:
                    bandStatus['status'] = False
                    bandStatus['message'] = '리더 승인 후'
                    break
            except Exception as e:
                print(str(e))
                pass


            try:
                wait_float(0.5, 1.0)
                joinBtn = driver.find_element(by=By.CSS_SELECTOR, value="._btnJoinBand")
                joinBtn.click()
            except Exception as e:
                print(str(e))
                pass

            try:
                wait_float(0.5, 1.0)
                joinQuestion = driver.find_element(by=By.CSS_SELECTOR, value=".modalHeader")
                if '가입 질문' in joinQuestion.text:
                    joinAnswerArea = driver.find_element(by=By.CSS_SELECTOR, value="._joinAnswer")
                    joinAnswerArea.send_keys('알겠습니다.')
                
                    wait_float(0.5,1.2)
                    confirmBtn = driver.find_element(by=By.CSS_SELECTOR, value="._confirmBtn")
                    confirmBtn.click()
            except Exception as e:
                print(str(e))
                pass


            

            
            # 모달 떠있으면 break!!
            try:
                print('모달 떠있다!!')
                wait_float(0.5, 1.0)
                joinModalChk = driver.find_element(by=By.CSS_SELECTOR, value=".lyContent")
                headingMsg = joinModalChk.find_element(by=By.CSS_SELECTOR, value=".headingMsg")
                if '1일 가입' in headingMsg.text:
                    print('오늘 가입 가능한 밴드 수 초과!!')
                    bandStatus['status'] = False
                    break
                elif '번호 인증' in headingMsg.text:
                    bandStatus['status'] = False
                    bandStatus['message'] = '인증 후 가입 가능'
                    break
                elif '제한' in headingMsg.text:
                    bandStatus['status'] = False
                    bandStatus['message'] = '밴드 가입 제한'
                    break
                elif '초과' in headingMsg.text:
                    bandStatus['status'] = False
                    bandStatus['message'] = '멤버수 초과'
                    break
                elif joinModalChk:
                    break
            except Exception as e:
                print(str(e))
                break




            

        if bandStatus['status'] == False:
            return bandStatus
        # 프로필 여러개일 시 프로필 리스트 가져오기!!
        errCount = 0
        while True:
            errCount += 1
            if errCount > 10:
                pg.press('enter')
                errStatus = True
            print('프로필 선택!!')
            try:
                wait_float(1.2, 1.5)
                profileList = driver.find_elements(by=By.CSS_SELECTOR, value=".textEllipsis")
                if len(profileList) > 0:
                    break
            except Exception as e:
                print(str(e))
                pass
            if errStatus:
                break
        
        if errStatus:
            continue

        # 프로필 이름 대조 > 있으면 radio input 클릭!!
        for i, p in enumerate(profileList):
            if p.text == profile:

                while True:
                    profileRadioList = driver.find_elements(by=By.CSS_SELECTOR, value=".checkInput._radio")
                    profileRadioList[i].click()
                    break
                profileSuccessStatus = True
                break

        if profileSuccessStatus == False:
            while True:
                print('새 프로필 만들기!!')

                # 새 프로필 버튼 클릭
                try:
                    wait_float(0.5, 1.0)
                    newProfileBtn = driver.find_element(by=By.CSS_SELECTOR, value="._newProfileBtn")
                    newProfileBtn.click()
                except:
                    pass

                # 프로필 INPUT 창 체크 후 프로필 복붙 하기!
                try:
                    focus_window('Chrome')
                    wait_float(0.5, 1.0)
                    profileNameInputBtn = driver.find_element(by=By.CSS_SELECTOR, value=".uInput")
                    if profileNameInputBtn:
                        cb.copy(profile)
                        wait_float(0.5,1.2)
                        profileNameInputBtn.click()
                        wait_float(0.5,1.2)
                        pg.hotkey('ctrl', 'v')
                        wait_float(0.5, 1.2)
                        profileNameInputBtn.send_keys(profile)
                except:
                    pass
                try:
                    profileNameInputBtnChk = driver.find_element(by=By.CSS_SELECTOR, value="._nameInput")
                    if profileNameInputBtnChk.get_attribute('value') == profile:
                        break
                    else:
                        continue
                except:
                    continue

            
        # 가입하기 버튼 클릭하기! (새 프로필 생성할때는 가입하기 버튼이 두개임!!)
        while True:
            print('가입하기 클릭!!')
            try:
                confirmSuccessStatus = False
                wait_float(0.5, 1.0)
                confirmBtns = driver.find_elements(by=By.CSS_SELECTOR, value="._confirmBtn")
                for confirmBtn in confirmBtns:
                    try:
                        confirmBtn.click()
                        confirmSuccessStatus = True
                    except:
                        pass
                if confirmSuccessStatus:
                    break
            except Exception as e:
                continue

        # alert 창 뜨면 확인 버튼 클릭
        try:
            wait_float(0.5, 1.0)
            alert = driver.switch_to.alert
            print("알림 내용:", alert.text)
            alert.accept() # 또는 alert.dismiss()
        except:
            pass



def naverLogin(driver, id, pwd):

    try:
        pg.moveTo(650, 160, duration=0.2)
        pg.leftClick()
    except:
        pass

    while True:
        wait_float(1.5, 2.5)
        try:
            loginBtn = driver.find_element(by=By.CSS_SELECTOR, value="._loginBtn")
            loginBtn.click()
            break
        except Exception as e:
            print(e)
            pass

        # 바로 로그인 종류 선택 페이지로 넘어가는경우 break
        try:
            keepLoggedChk = driver.find_elements(by=By.CSS_SELECTOR, value=".uCheckbox span")
            if len(keepLoggedChk) > 0:
                break
        except Exception as e:
            print(e)
            pass

        # 바로 밴드 메인으로 가는경우 return
        try:
            logginedChk = driver.find_elements(by=By.CSS_SELECTOR, value=".inputBandSearch")
            if len(logginedChk) > 0:
                return
        except Exception as e:
            print(e)
            pass

        

        

    
    while True:
        wait_float(0.5,1.2)
        try:
            keepLogged = driver.find_element(by=By.CSS_SELECTOR, value=".uCheckbox span")
            keepLogged.click()
        except Exception as e:
            print(e)
            pass

        try:
            keepLogged = driver.find_element(by=By.CSS_SELECTOR, value=".uCheckbox span")
            print(keepLogged.get_attribute('class'))
            if keepLogged.get_attribute('class') == 'checked':
                break
        except Exception as e:
            print(e)
            pass
         


    while True:
        wait_float(1.5, 2.5)
        try:
            naverLoginBtn = driver.find_element(by=By.CSS_SELECTOR, value=".-naver.externalLogin")
            naverLoginBtn.click()
            break
        except Exception as e:
            print(e)
            pass


    
    while True:
        focus_window('Chrome')
        wait_float(1.5, 2.5)
        try:
            idInput = driver.find_element(by=By.CSS_SELECTOR, value="#id")

            cb.copy(id)
            wait_float(0.5,1.2)
            idInput.click()
            wait_float(0.5,1.2)
            pg.hotkey('ctrl', 'v')
            wait_float(0.5, 1.2)
        except:
            continue
        try:
            pwdInput = driver.find_element(by=By.CSS_SELECTOR, value="#pw")

            cb.copy(pwd)
            wait_float(0.5,1.2)
            pwdInput.click()
            wait_float(0.5,1.2)
            pg.hotkey('ctrl', 'v')
            wait_float(0.5, 1.2)
        except:
            pass

        try:
            loginSuccessBtnActiveChk = driver.find_elements(by=By.CSS_SELECTOR, value=".btn_login.next_step.nlog-click.off")
            if len(loginSuccessBtnActiveChk) == 0:
                loginSuccessBtnActive = driver.find_element(by=By.CSS_SELECTOR, value=".btn_login.next_step.nlog-click")
                loginSuccessBtnActive.click()
                break
        except:
            pass
    
    while True:
        wait_float(0.5,1.2)
        try:
            bandMainChk = driver.find_elements(by=By.CSS_SELECTOR, value=".inputBandSearch")
            print(f'bandMainChk : {bandMainChk}')
            if len(bandMainChk) > 0:
                break
        except:
            pass

        try:

            sel = 'iframe[style*="width: 400px"][style*="height: 580px"]'
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            print(f"ifram elements : {elements}")
            if elements:            # 리스트가 비어있지 않으면 True
                pg.alert('캡챠 확인!!!!!!!!!!')
                break
        except:
            pass


        
        




def wait_float(start, end):
    wait_ran = random.uniform(start, end)
    time.sleep(wait_ran)


def focus_window(title_substr: str):
    """제목에 특정 문자열이 포함된 창을 찾아 활성화"""
    windows = gw.getWindowsWithTitle(title_substr)
    if not windows:
        print(f"'{title_substr}' 가 포함된 창을 찾을 수 없습니다.")
        return False

    win = windows[0]  # 첫 번째 매칭된 창
    win.activate()    # 해당 창 활성화
    print(f"창 활성화: {win.title}")
    return win

def list_windows():
    """현재 열려있는 모든 창 제목 출력"""
    titles = gw.getAllTitles()
    print("=== 현재 열려있는 창 목록 ===")
    for i, t in enumerate(titles):
        if t.strip():  # 빈 문자열 제외
            print(f"{i}: {t}")
    return titles



def is_window_open(title_substr: str) -> bool:
    return any(title_substr.lower() in (t or "").lower() for t in gw.getAllTitles())