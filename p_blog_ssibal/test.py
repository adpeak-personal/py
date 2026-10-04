from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

import threading
from tkinter import *
from tkinter import ttk
import pyautogui as pg



try:
    print('들어는 옴?! 111')
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    print('들어는 옴?! 222')
    # 기존 Chrome 세션에 연결
    driver = webdriver.Chrome(options=chrome_options)
    print('들어는 옴?! 333')
    # 이제 driver 객체를 사용하여 열려 있는 Chrome 브라우저를 제어할 수 있습니다.
    # 예시: 현재 페이지의 제목 출력
    print(driver.title)
    print('들어는 옴?! 444')
    # 예시: 특정 웹사이트로 이동
    

    pg.alert('잠깐만!!!!')

    while True:
        driver.get("https://www.naver.com")
        try:
            gotoLogin = driver.find_element(by=By.CSS_SELECTOR, value="#query")
            print(gotoLogin)
            pg.alert('대기요!!!')
        except Exception as e:
            print('로그인 버�� ��기 실��')
            break

    # 로그인 완료 되었는지 체크!
    while True:
        try:
            loginChk = driver.find_elements(by=By.CSS_SELECTOR, value=".MyView-module__btn_logout___bsTOJ")
            if len(loginChk) > 0:
                break
            else:
                pg.alert('로그인을 완료 해주세요')
        except Exception as e:
            print('로그인 찾기 에러~~~')
            break

    
    # 블로그 탭 가기
    while True:
        try:
            mainBtns = driver.find_elements(by=By.CSS_SELECTOR, value=".shortcut_item")
            for btn in mainBtns:
                if '블로그' in btn.text:
                    btn.click()
                    break
        except Exception as e:
            print('로그인 찾기 에러~~~')
            break

        try:
            handles = driver.window_handles
            pg.alert(len(handles))
            first_tab = handles[0]
        except Exception as e:
            print('로그인 찾기 에러~~~')
            break



    
    
    

    

    # 작업 완료 후 브라우저를 닫지 않으려면 driver.quit() 또는 driver.close()를 호출하지 않습니다.
    # 스크립트가 종료되어도 브라우저는 계속 열려 있습니다.
except Exception as e:
    print