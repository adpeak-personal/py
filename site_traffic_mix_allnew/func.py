import random
import threading
from datetime import datetime
import sys
import tempfile, shutil, psutil, subprocess, os, time
from ppadb.client import Client as AdbClient
import requests
import clipboard as cb
import pyautogui as pg

import ctypes
import pygetwindow as gw
from pywinauto import Desktop
from pywinauto.application import Application
from tkinter import *
import tkinter as tk
from tkinter import ttk

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from urllib.parse import urlparse, parse_qs

test = None
# test = "ok"



# def changeIp():
#     getIp = ""
#     try:
#         print('아이피 변경 언제??')
#         os.system('adb server start')
#         client = AdbClient(host="127.0.0.1", port=5037)
#         device = client.devices()  # 디바이스 1개
#         if len(device) == 0:
#             print('디바이스가 없냐 왜;;;')

#         print(device)
#         ondevice = device[0]
#         print(f"온디바이스ondevice : {ondevice}")
#         ondevice.shell("input keyevent KEYCODE_POWER")
#         ondevice.shell("svc data disable")
#         ondevice.shell("settings put global airplane_mode_on 1")
#         ondevice.shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true")
#         time.sleep(0.5)
#         ondevice.shell("svc data enable")
#         ondevice.shell("settings put global airplane_mode_on 0")
#         ondevice.shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false")
#         print('아이피 변경 함??')
#         time.sleep(3)
#         success, res = request_safely_get("https://api.ip.pe.kr/json/")
#         return res['ip']
#     except Exception as e:
#         print(str(e))
#         pass


def changeIp():
    try:
        print('아이피 변경 언제??')
        
        os.system('adb kill-server')
        time.sleep(0.5)
        os.system('adb start-server')
        time.sleep(1)
        
        client = AdbClient(host="127.0.0.1", port=5037)
        
        device = []
        exception_holder = [None]
        
        def get_devices():
            try:
                result = client.devices()
                device.extend(result)
            except Exception as e:
                exception_holder[0] = e
        
        thread = threading.Thread(target=get_devices)
        thread.daemon = True
        thread.start()
        thread.join(timeout=5)
        
        if thread.is_alive():
            print("ADB 응답 타임아웃! 5초 경과")
            return None
        
        if exception_holder[0]:
            print(f"디바이스 조회 에러: {exception_holder[0]}")
            return None
        
        # 에뮬레이터 제외하고 실제 디바이스만 필터링
        real_devices = [d for d in device if not d.serial.startswith('emulator-')]
        
        print(f"전체 디바이스: {len(device)}개")
        print(f"실제 휴대폰: {len(real_devices)}개")
        
        if len(real_devices) == 0:
            print('실제 휴대폰이 연결되지 않음!')
            return None
        
        ondevice = real_devices[0]
        print(f"사용할 디바이스: {ondevice.serial}")
        
        # 화면 켜기
        ondevice.shell("input keyevent KEYCODE_POWER")
        time.sleep(0.3)
        
        # 비행기 모드 ON
        ondevice.shell("svc data disable")
        ondevice.shell("settings put global airplane_mode_on 1")
        ondevice.shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true")
        time.sleep(1.5)
        
        # 비행기 모드 OFF
        ondevice.shell("settings put global airplane_mode_on 0")
        ondevice.shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false")
        ondevice.shell("svc data enable")
        
        print('아이피 변경 완료')
        time.sleep(3)
        
        success, res = request_safely_get("https://api.ip.pe.kr/json/")
        if success and res and 'ip' in res:
            print(f"새 IP: {res['ip']}")
            return res['ip']
        else:
            print("IP 조회 실패")
            return None
        
    except Exception as e:
        print(f"에러 발생: {str(e)}")
        return None



def wait_float(start, end):
    wait_ran = random.uniform(start, end)
    time.sleep(wait_ran)


def wait_float_timer(start, end, show=True):
    wait_ran = random.uniform(start, end)
    total = int(wait_ran)

    if show:
        print(f"[INFO] 대기 시작: {wait_ran:.2f}초 예정")

    for sec in range(total, 0, -1):
        if show:
            print(f"[INFO] 남은 시간: {sec}초")
        time.sleep(1)

    # 잔여 소수점(0~1초 미만)도 정확히 기다림
    remainder = wait_ran - total
    if remainder > 0:
        time.sleep(remainder)

    if show:
        print("[INFO] 대기 완료 ✅")



# driver.quit() 대신 사용! (크롬 드라이버 및 크롬 프로세스 완전 종료)
def close_driver(driver, service, user_data_dir):
    # 1) 정상 종료 시도
    print("1) 정상 종료 시도")
    try: driver.quit()
    except: pass
    time.sleep(0.3)

    # 2) chromedriver 및 자식 프로세스 강제 종료 (내가 띄운 것만)
    print("2) chromedriver 및 자식 프로세스 강제 종료 (내가 띄운 것만)")
    try:
        if service and service.process:
            p = psutil.Process(service.process.pid)
            # 자식부터 kill
            for child in p.children(recursive=True):
                try: child.kill()
                except: pass
            try: p.kill()
            except: pass
    except: pass

    # 3) 혹시 남은 Chrome 중에 "내 user-data-dir"을 쓰는 것만 골라서 kill
    print("3) 혹시 남은 Chrome 중에 '내 user-data-dir'을 쓰는 것만 골라서 kill")
    try:
        for proc in psutil.process_iter(["pid","name","cmdline"]):
            name = (proc.info["name"] or "").lower()
            cmd  = " ".join(proc.info.get("cmdline") or [])
            if "chrome" in name and user_data_dir and user_data_dir in cmd:
                try: proc.kill()
                except: pass
    except: pass

    # 4) 임시 프로필 폴더 정리
    print('4) 임시 프로필 폴더 정리')
    try: shutil.rmtree(user_data_dir, ignore_errors=True)
    except: pass


def focus_target_chrome(driver, title_parts):
    """
    driver: selenium webdriver (Chrome)
    title_parts: ['네이버', '검색'] 처럼 '모두' 포함돼야 매칭

    동작:
    1. selenium이 열어둔 창/탭 중에서 title_parts 전부 들어간 창 찾기
    2. 찾으면 그 창으로 switch
    3. OS 레벨에서 그 크롬 창에 포커스 맞춤
    4. 그 창을 제외한 '다른 크롬 창'은 전부 닫음 (사람이 연 크롬도 포함)
    5. 성공하면 True, 없으면 False
    """
    target_handle, target_title = _find_driver_window(driver, title_parts)
    if not target_handle:
        return False

    # 2) selenium 내부 포커스
    driver.switch_to.window(target_handle)

    # 3~4) OS 레벨 처리
    _focus_and_close_other_chromes(target_title)

    return True


def _find_driver_window(driver, title_parts):
    """
    Selenium이 관리하는 window_handles 중에서 title_parts 전부 포함하는 창 찾기
    """
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        title = (driver.title or "").strip()
        if all(part in title for part in title_parts):
            return handle, title
    return None, None


def _focus_and_close_other_chromes(target_title: str) -> None:
    """
    pywinauto로 떠 있는 크롬 창들을 순회해서
    - target_title 이 들어간 크롬은 살리고 포커스
    - 나머지 크롬은 전부 닫는다
    """
    try:
        from pywinauto import Desktop
    except ImportError:
        # pywinauto 없으면 OS 레벨 처리는 패스
        return

    desktop = Desktop(backend="uia")

    target_win = None
    windows = desktop.windows()

    # 1) 먼저 '살릴' 크롬 찾기
    for w in windows:
        wt = w.window_text()
        # 크롬 판별을 너무 빡세게 하면 안 되니까 느슨하게
        if ('Chrome' in wt or 'Google Chrome' in wt) and target_title in wt:
            target_win = w
            break

    # 포커스 먼저
    if target_win is not None:
        try:
            target_win.set_focus()
        except Exception:
            pass

    # 2) 이제 다른 크롬 창들 닫기
    for w in windows:
        wt = w.window_text()
        # 크롬 아니면 스킵
        if not ('Chrome' in wt or 'Google Chrome' in wt):
            continue

        # 내가 살리기로 한 창이면 스킵
        if target_win is not None and w.handle == target_win.handle:
            continue

        # 여기까지 왔으면 닫아도 되는 크롬
        try:
            w.close()
        except Exception:
            # 어떤 창은 닫기 막혀있을 수 있음 → 무시
            pass



def create_active_array(lengthArr, innerArr):
    # 배열의 길이는 랜덤한 값을 사용
    length = random.randint(lengthArr[0], lengthArr[1])
    
    # 기본적으로 모두 'notWork'로 채운다
    array = ['notWork'] * length
    
    # 첫 번째와 마지막 요소는 'notWork'로 유지
    array[0] = 'notWork'
    array[-1] = 'notWork'
    
    # 'work'의 개수를 랜덤으로 결정
    num_of_works = random.randint(innerArr[0], innerArr[1])
    
    # 첫 번째와 마지막 요소를 제외한 인덱스 리스트
    available_positions = list(range(1, length - 1))
    
    # 무작위로 num_of_works개의 위치를 선택하여 'work'로 설정
    work_positions = random.sample(available_positions, num_of_works)
    
    for pos in work_positions:
        array[pos] = 'work'
    
    # 'work' 위치 중 하나를 선택하여 'realwork'로 변경
    if work_positions:  # work_positions가 비어 있지 않은지 확인
        realwork_position = random.choice(work_positions)
        array[realwork_position] = 'realwork'
    
    return array

def create_active_array_many(lengthArr, innerArr, num_realworks=1):
    length = random.randint(lengthArr[0], lengthArr[1])
    array = ['notWork'] * length
    array[0] = 'notWork'
    array[-1] = 'notWork'
    
    available_positions = list(range(1, length - 1))
    
    # 뽑을 수 있는 개수보다 크게 안 뽑게 보정
    num_of_works = min(random.randint(innerArr[0], innerArr[1]), len(available_positions))
    
    work_positions = random.sample(available_positions, num_of_works)
    for pos in work_positions:
        array[pos] = 'work'
    
    if work_positions:
        num_realworks = min(num_realworks, len(work_positions))
        realwork_positions = random.sample(work_positions, num_realworks)
        for pos in realwork_positions:
            array[pos] = 'realwork'
    
    return array




def request_safely_get(site_link: str, timeout: int = 10, retry_delay: int = 3, max_retries: int = None):
    """
    서버에서 not work 정보를 안전하게 로드하는 함수
    
    Args:
        site_link: API 서버 링크
        timeout: 요청 타임아웃 (초)
        retry_delay: 재시도 대기 시간 (초)
        max_retries: 최대 재시도 횟수 (None이면 무제한)
    
    Returns:
        Tuple[bool, dict]: (성공여부, 응답데이터)
    """
    retry_count = 0
    
    while True:
        try:
            print('요청 시작!!')
            
            # 타임아웃 설정으로 무한 대기 방지
            response = requests.get(
                site_link,
                timeout=timeout
            )
            
            # HTTP 상태 코드 확인
            response.raise_for_status()
            
            # JSON 파싱
            res = response.json()
            print('요청 완료!')
            print(res)
            
            # status 또는 result가 True인지 확인
            status_ok = res.get('status') == True
            result_ok = res.get('result') == True
            
            if status_ok or result_ok:
                return (True, res)
            else:
                # 둘 다 False면 재시도
                print(f'status와 result가 모두 False입니다. {retry_delay}초 후 재시도...')
                time.sleep(retry_delay)
                continue
                
        except requests.exceptions.Timeout:
            print(f'타임아웃 발생! {retry_delay}초 후 재시도...')
            
        except requests.exceptions.ConnectionError:
            print(f'연결 오류 발생! {retry_delay}초 후 재시도...')
            
        except requests.exceptions.HTTPError as e:
            print(f'HTTP 오류 발생: {e}. {retry_delay}초 후 재시도...')
            
        except requests.exceptions.RequestException as e:
            print(f'요청 오류 발생: {e}. {retry_delay}초 후 재시도...')
            
        except ValueError as e:
            print(f'JSON 파싱 오류: {e}. {retry_delay}초 후 재시도...')
            
        except Exception as e:
            print(f'예상치 못한 오류 발생: {str(e)}. {retry_delay}초 후 재시도...')
        
        # 재시도 카운트 증가
        retry_count += 1
        if max_retries is not None and retry_count >= max_retries:
            print(f'최대 재시도 횟수({max_retries})에 도달했습니다.')
            return (False, {})
        
        # 재시도 전 대기
        time.sleep(retry_delay)



def load_notwork_safely_post(site_link: str, data = None, timeout: int = 10, retry_delay: int = 3, max_retries: int = None):
    """
    서버에서 not work 정보를 안전하게 로드하는 함수 (POST 버전)
    
    Args:
        site_link: API 서버 링크
        data: POST 요청에 포함할 데이터 (dict)
        timeout: 요청 타임아웃 (초)
        retry_delay: 재시도 대기 시간 (초)
        max_retries: 최대 재시도 횟수 (None이면 무제한)
    
    Returns:
        Tuple[bool, dict]: (성공여부, 응답데이터)
    """
    retry_count = 0
    
    if data is None:
        data = {}
    
    while True:
        try:
            # 타임아웃 설정으로 무한 대기 방지
            response = requests.post(
                site_link,
                json=data,
                timeout=timeout
            )
            
            # HTTP 상태 코드 확인
            response.raise_for_status()
            
            # JSON 파싱
            res = response.json()
            print('now work 정보!')
            print(res)
            
            # status 키가 있는지 확인
            if 'status' not in res:
                print('경고: status 키가 응답에 없습니다.')
                time.sleep(retry_delay)
                continue
            
            # status가 True일 때만 성공으로 처리
            if res['status'] == True:
                return (True, res)
            else:
                # status가 False면 재시도
                print(f'status가 False입니다. {retry_delay}초 후 재시도...')
                time.sleep(retry_delay)
                continue
                
        except requests.exceptions.Timeout:
            print(f'타임아웃 발생! {retry_delay}초 후 재시도...')
            
        except requests.exceptions.ConnectionError:
            print(f'연결 오류 발생! {retry_delay}초 후 재시도...')
            
        except requests.exceptions.HTTPError as e:
            print(f'HTTP 오류 발생: {e}. {retry_delay}초 후 재시도...')
            
        except requests.exceptions.RequestException as e:
            print(f'요청 오류 발생: {e}. {retry_delay}초 후 재시도...')
            
        except ValueError as e:
            print(f'JSON 파싱 오류: {e}. {retry_delay}초 후 재시도...')
            
        except Exception as e:
            print(f'예상치 못한 오류 발생: {str(e)}. {retry_delay}초 후 재시도...')
        
        # 재시도 카운트 증가
        retry_count += 1
        if max_retries is not None and retry_count >= max_retries:
            print(f'최대 재시도 횟수({max_retries})에 도달했습니다.')
            return (False, {})
        
        # 재시도 전 대기
        time.sleep(retry_delay)





class HistoryTracker:
    def __init__(self):
        self.history_count = 0
        self.current_position = 0
    
    def record_navigation(self):
        """페이지 이동 시 호출"""
        self.history_count += 1
        self.current_position = self.history_count
        print(f"[INFO] 히스토리 기록: {self.current_position}/{self.history_count}")
    
    def record_back(self):
        """뒤로가기 시 호출"""
        if self.current_position > 1:
            self.current_position -= 1
        print(f"[INFO] 뒤로가기: {self.current_position}/{self.history_count}")
        return self.can_go_back()
    
    def can_go_back(self):
        """뒤로갈 수 있는지 확인"""
        return self.current_position > 1
    
    def back_count_available(self):
        """뒤로갈 수 있는 횟수"""
        return self.current_position - 1
    


# 네이버 검색 함수! PC / 모바일 동일!
def naverSearch(driver, keyword):
    # 시작!!! 네이버 검색!!

    errCount = 0
    while True:

        wait_float_timer(0,1)
        pg.moveTo(20,110)
        pg.leftClick()

        errCount += 1
        # 5회 이상 오류시 F5 새로고침
        if errCount > 5:
            pg.press('F5')
            wait_float_timer(3,4)
        # 10회 이상 오류시 네이버 메인으로 강제 이동
        elif errCount > 10:
            driver.get('https://www.naver.com')
            wait_float_timer(3,4)
            focus_target_chrome(driver, ['NAVER'])
            errCount = 0
        else:
            focus_target_chrome(driver, ['네이버','검색'])
        

        

        try:
            wait_float(0.5,0.8)
            mainSearchTab = driver.find_element(by=By.CSS_SELECTOR, value="#MM_SEARCH_FAKE")
            mainSearchTab.click()
        except Exception as e:
            print('#MM_SEARCH_FAKE 찾기 오류')
            pass

        try:
            wait_float(0.5,0.8)
            subSearchTab = driver.find_element(by=By.CSS_SELECTOR, value="#query")
            subSearchTab.click()
        except Exception as e:
            print('#query 찾기 오류')
            pass

        try:
            wait_float(0.5,0.8)
            subSearchTab = driver.find_element(by=By.CSS_SELECTOR, value="#nx_query")
            subSearchTab.click()
        except Exception as e:
            print('#nx_query 찾기 오류')
            pass

        try:
            wait_float(1.2,1.9)
            pg.hotkey('ctrl', 'a')
            pg.press('delete')
            wait_float(1.2,1.9)
            cb.copy(keyword)
            pg.hotkey('ctrl', 'v')
            wait_float(1.2,1.9)
        except Exception as e:
            print('붙여넣기 오류')
            pass

        print('검색 붙여넣기 완료~')

        # 검색 완료 엔터!!!
        try:
            subSearchTab = driver.find_element(by=By.CSS_SELECTOR, value="#query")
            searchVal = subSearchTab.get_attribute('value')
            if searchVal is not None and searchVal == keyword:
                subSearchTab.send_keys(Keys.ENTER)
                break
        except Exception as e:
            print('#query 결과 찾기 오류')
            pass

        try:
            subSearchTab = driver.find_element(by=By.CSS_SELECTOR, value="#nx_query")
            searchVal = subSearchTab.get_attribute('value')
            
            if searchVal is not None and searchVal == keyword:
                subSearchTab.send_keys(Keys.ENTER)
                break
        except Exception as e:
            print('#nx_query 결과 찾기 오류')
            pass

        print('검색 엔터 완료!!')
    
    # 검색 창 제대로 나올때까지 대기 or F5
    while True:
        try:
            wait_float_timer(3,4)
            print('검색 확인 START!!!')
            focusChk = focus_target_chrome(driver, [keyword, '네이버', '검색'])
            subSearchTab1 = driver.find_elements(by=By.CSS_SELECTOR, value="#query")
            subSearchTab2 = driver.find_elements(by=By.CSS_SELECTOR, value="#nx_query")
            if focusChk and (len(subSearchTab1) > 0 or len(subSearchTab2) > 0):
                break
            else:
                pg.press('F5')
        except:
            pass

def clickScrollOtherMobile(driver,keyword):
    # 모바일 버전으로 작업시!!
    while True:
        try:
            sections = driver.find_elements(by=By.CSS_SELECTOR, value=".fds-default-mode")
            if len(sections) > 0:
                break
        except:
            pass
        
    onotherList = []  # [(text, WebElement), ...] 형태로 저장
    for sec in sections:
        # 1) 섹션 안에 fds-web-root 가 있으면 제외
        if sec.find_elements(By.CSS_SELECTOR, ".fds-web-root"):
            continue

        # 2) 없으면 타이틀 후보들 수집
        elems = sec.find_elements(By.CSS_SELECTOR,".fds-comps-right-image-text-title, .sds-comps-text-type-headline1")


        keywords = ["더보기", "찾는", "콘텐츠", "인기글", "지식", "동영상"]
        for el in elems:
            addStatus = True
            for keyword in keywords:
                if keyword in el.text:
                    addStatus = False
                
            if addStatus == True:
                onotherList.append(el)
    for data in onotherList:
        print(data.text)

    workOnotherVal = random.randrange(0, len(onotherList) - 1)
    forClickEle = onotherList.pop(workOnotherVal)
    driver.set_page_load_timeout(15)
    forClickEle.click()

    scrollRanVal = random.randrange(8, 15)
    for k in range(scrollRanVal):
        print('스크롤 중~~~')
        pg.moveTo(300,400)
        pg.scroll(-150)
        if test == 'ok':
            wait_float(0.1,0.5)
        else:
            wait_float(5.5,7.5)


def clickScrollOtherPC(driver,keyword):
    # PC 버전으로 작업시!!
    while True:
        try:
            sections = driver.find_elements(by=By.CSS_SELECTOR, value=".api_subject_bx")
            if len(sections) > 0:
                break
        except:
            pass

    onotherList = []  # [(text, WebElement), ...] 형태로 저장
    for sec in sections:
        # 1) 섹션 안에 fds-web-root 가 있으면 제외 (웹문서 영역)
        if sec.find_elements(By.CSS_SELECTOR, ".fds-web-root"):
            continue

        # 2) 없으면 타이틀 후보들 수집
        elems = sec.find_elements(
            By.CSS_SELECTOR,
            ".fds-comps-right-image-text-title, .sds-comps-text-type-headline1"
        )


        keywords = ["더보기", "찾는", "콘텐츠", "인기글", "지식", "동영상"]
        for el in elems:
            addStatus = True
            for keyword in keywords:
                if keyword in el.text:
                    addStatus = False
                
            if addStatus == True:
                onotherList.append(el)

    for data in onotherList:
        print(data.text)

    workOnotherVal = random.randrange(0, len(onotherList) - 1)
    forClickEle = onotherList.pop(workOnotherVal)
    driver.set_page_load_timeout(15)
    forClickEle.click()

    scrollRanVal = random.randrange(8, 15)
    for k in range(scrollRanVal):
        print('스크롤 중~~~')
        pg.moveTo(300,400)
        pg.scroll(-150)
        if test == 'ok':
            wait_float(0.1,0.5)
        else:
            wait_float(5.5,7.5)



def backToSearchMobile(driver,keyword):
    actNum = 0
    while True:
        actNum += 1
        try:
            current_url = driver.current_url
            focusChk = focus_target_chrome(driver, [keyword, '네이버', '검색'])
            naverChk = focus_target_chrome(driver, ['NAVER'])
            print(focusChk)
            print(naverChk)
            if focusChk or naverChk:
                print('체크 확인! break')
                break
            else:
                print('체크 체크 안됨! 다음으로!')
                if actNum % 2 == 0:
                    driver.forward()
                else:
                    driver.execute_script("window.history.foward()")
            wait_float_timer(2,3)

            print('URL 동일한지 비교!')
            if driver.current_url == current_url:
                print('URL 이 동일!!')
                if actNum % 5 == 0:
                    pg.moveTo(30,60)
                    pg.leftClick()
                elif actNum % 2 == 0:
                    driver.back()
                else:
                    driver.execute_script("window.history.back()")
            wait_float_timer(3,4)
        except:
            pass



def backToSearchPC(driver,keyword):
    while True:
        focusChk = focus_target_chrome(driver, [keyword, '네이버', '검색'])
        if focusChk:
            break



def searchContentInnerWork(driver, webClass, loadLink, sameLink, workType):


    returnVal = {"status" : False , "rate" : 0}
    try:
        targetList = driver.find_elements(by=By.CSS_SELECTOR, value=f"{webClass}")
        actTarget = ""
        print(targetList)
        for idx, target in enumerate(targetList):
            getHref = target.get_attribute('href')
            st_link = str(loadLink).strip()
            getHref = getHref.strip()

            print(getHref)
            wait_float(0.3,0.7)

            if sameLink:
                if st_link == getHref:
                    returnVal['rate'] = idx + 1
                    print('여기까지 왔다!!')
                    actTarget = target
                    # workInfo['work_type'] 이 클릭이면 클릭 / 아니면 그냥 해당 위치로 스크롤만 하고 패스~
                    returnVal['status'] = True
                    break
            else:
                if st_link in getHref:
                    returnVal['rate'] = idx + 1
                    actTarget = target
                    # workInfo['work_type'] 이 클릭이면 클릭 / 아니면 그냥 해당 위치로 스크롤만 하고 패스~
                    returnVal['status'] = True
                    break
    except:
        pass

    if returnVal['status'] == True:
        wait_float(1.2,1.5)
        browserMiddleMoveJsCode = """
        var element = arguments[0];
        var elementRect = element.getBoundingClientRect();
        var absoluteElementTop = elementRect.top + window.pageYOffset;
        var middle = absoluteElementTop - (window.innerHeight / 2);
        window.scrollTo({ top: middle, behavior: 'smooth'});
        """
        driver.execute_script(browserMiddleMoveJsCode, actTarget)
        wait_float(1.2,1.5)
        print('위치로 갔다잉~')

        if workType == 'click':
            while True:
                try:
                    actTarget.click()
                    break
                except:
                    wait_float(0.5,1.2)
                    pg.scroll(-150)
                    pass
            
            scrollRanVal = random.randrange(8, 15)
            for k in range(scrollRanVal):
                pg.moveTo(300,400)
                pg.scroll(-150)
                if test == 'ok':
                    wait_float(0.1,0.5)
                else:
                    wait_float(5.5,7.5)

    return returnVal



# 
def searchContentRate(driver, workType, workInfo, type='view', env="mobile"):

    returnVal = {"status" : False , "rate" : ""}
    page = 1
    # 먼저 메인 페이지에서 2번 검색 시도!!
    for i in range(2):
        rateWorkChk = searchContentInnerWork(driver, workType['web_class'], workInfo['st_link'], workInfo['st_same_link'], type)
        if rateWorkChk['status']:
            returnVal = {"status" : True , "rate" : f"{page}/{rateWorkChk['rate']}"}
            if type == 'click':
                if env == 'pc':
                    backToSearchPC(driver, workInfo['st_subject'])
                else:
                    backToSearchMobile(driver, workInfo['st_subject'])
            break

    # 메인 페이지에 없으면 페이징 시작하기!!
    if rateWorkChk['status'] == False:

        # 먼저 검색 결과 탭으로 이동!! (이동하면 자동으로 2페이지)
        while True:
            wait_float_timer(1,2)
            try:
                btns1 = driver.find_elements(by=By.CSS_SELECTOR, value=f".sds-comps-footer-content")
                for btn in btns1:
                    print(btn.text)
                    if '검색결과' in btn.text:
                        btn.click()
            except:
                pass
            try:
                linkMore = driver.find_element(by=By.CSS_SELECTOR, value=f".link_feed_more")
                linkMore.click()
            except:
                pass
            wait_float_timer(1,2)
            current_url = driver.current_url

            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            where = query_params.get('where', [None])[0]

            if env == 'pc':
                if where == 'web':
                    break
            else:
                if where == 'm_web':
                    break

            pg.moveTo(20,110)
            pg.leftClick()
            pg.press('end')

        # 페이지 이동 완료 했으면 검색 > 없으면 페이지 이동 > 반복 순으로 10페이지까지 시도!
        for i in range(2, 11):
            page = i
            rateWorkChk = searchContentInnerWork(driver, workType['web_class'], workInfo['st_link'], workInfo['st_same_link'], type)
            if rateWorkChk['status']:
                returnVal = {"status" : True , "rate" : f"{page}/{rateWorkChk['rate']}"}
                if type == 'click':
                    if env == 'pc':
                        backToSearchPC(driver, workInfo['st_subject'])
                    else:
                        backToSearchMobile(driver, workInfo['st_subject'])
                break
            else:
                if i < 10:
                    wait_float_timer(1,2)
                    while True:
                        try:
                            if env == 'pc':
                                pageBtns = driver.find_elements(by=By.CSS_SELECTOR, value=f".sc_page_inner a")
                            else:
                                pageBtns = driver.find_elements(by=By.CSS_SELECTOR, value=f".list_page a")
                            for btn in pageBtns:
                                print(btn.text)
                                if str(page + 1) == btn.text:
                                    btn.click()
                                    break
                            
                            current_url = driver.current_url
                            parsed_url = urlparse(current_url)
                            query_params = parse_qs(parsed_url.query)
                            nowPage = query_params.get('page', [None])[0]
                            if nowPage == str(page + 1):
                                break
                        except:
                            pass
                    print(f'{page + 1}페이지 도착 완료!!!')
                else:
                    break
    return returnVal

