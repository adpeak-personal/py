import random
import threading
import time
import datetime
import sys
import os
from pathlib import Path
import math
# from typing import Optional
# from pyparsing import And
import requests
import urllib.request
from urllib.parse import urlparse
# from bs4 import BeautifulSoup as bs
import json
import re
import pyautogui as pg
import ctypes
from bs4 import BeautifulSoup
from tkinter import *
from tkinter import ttk
import winsound as ws
import winsound as sd
import shutil
import getpass
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.service import Service as ChromeService
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException
import clipboard as cb
import random
import pygetwindow as gw
from pywinauto import Desktop
import pyperclip


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path  # netloc이 없으면 path 사용
    # www. 제거
    domain = domain.replace("www.", "")
    return domain

def getNewsContent(siteLink, client_id, client_secret, keyword = "이슈"):

    while True:
        try:
            newsListRes = requests.get(f"{siteLink}/api/v7/res/get_news_list").json()
            if newsListRes['status'] == True:
                newsList = [item['un_content'] for item in newsListRes['news_list']]
                break
        except:
            pass

    resultItem = None
    while True:
        try:
            encText = urllib.parse.quote(keyword) # 검색할 키워드
            url = "https://openapi.naver.com/v1/search/news?query=" + encText # json 결과가 필요할 때 사용

            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            response = urllib.request.urlopen(request)
            rescode = response.getcode()
            response_body = response.read()
            newsObj = json.loads(response_body.decode('utf-8'))
            for item in newsObj['items']:
                if "naver.com" in item["link"]:
                    # 서버에서 가져온 newsList 안에 item["link"]가 포함되어 있지 않을때 break
                    resLink = item["link"].replace('&','-')
                    if resLink not in newsList:
                        resultItem = item
                        break
            if resultItem is None:
                return False
            else:
                # 구한 기사 아이템은 서버에 보내서 기록
                errCount = 0
                while True:
                    errCount += 1
                    if errCount > 5:
                        resultItem = None
                        return
                    try:
                        addUsedNewsRes = requests.get(f"{siteLink}/api/v7/res/add_news_work?addnewslink={resLink}").json()
                        if addUsedNewsRes['status'] == True:
                            break
                    except:
                        pass
                return resultItem
        except Exception as e:
            print(str(e))
            pass

def replaceText(text):
    pattern = r'\([^)]*\)|\[[^\]]*\]|<[^>]*>|[&!@#$%^&*()]|\n+| +|,|`|"\'\'\'"|"\'\'"|"\.\.\."|"\'"|\''
    result = re.sub(pattern, ' ', text)
    result = result.replace("  "," ")
    result = result.replace("  "," ")
    result = result.replace("  "," ")
    result = result.replace("  "," ")
    result = result.replace("  "," ")
    replaceList = ["…", "…","↑","·","...","‘","’","?","“","”","[","(","<",'"',"△","●","amp;","《","》","━","◆","◇","▶","♥","♡","★","☆","■","↓","섹스","조까","18년","쓰바","개년","이렉트","스팽","좆","좇","좃","졷","씹","씨발","18년","18","아가리","확률","oPtA","캐나다","1억","화상","섹스","조까","18년","쓰바","니미","시불","씨불","quot;","ⓒ"]
    for replaceCon in replaceList:
        result = result.replace(replaceCon," ")

    result = result.strip()
    
    return result

def getArticleContent(link):
    response = requests.get(link)
    if response.status_code == 200:
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        wait_float(0.3,0.9)

    try:
            imgPhotos = soup.find_all(class_="end_photo_org")
            for imgPhoto in imgPhotos:
                imgPhoto.decompose()
    except:
        pass

    delClassList = ['caption', 'source', 'byline', 'article_notice_txt', 'reporter_area', 'copyright', 'promotion', 'artical-btm']
    for delClass in delClassList:
        try:
            delTag = soup.find(class_=delClass)
            delTag.decompose()
        except:
            pass

    try:
        delTag = soup.find(id="_article_section_guide")
        delTag.decompose()
    except:
        pass
    
    try:
        article1 = clean_text(soup.select_one('#articeBody').get_text())
        article = replaceText(article1)
    except Exception as e:
        print(str(e))
        pass

    try:
        articleArea = soup.find(class_='news_end')
        article = replaceText(articleArea.text)

    except Exception as e:
        print(str(e))
        pass

    try:
        articleArea = soup.find(id='dic_area')
        article = replaceText(articleArea.text)
    except Exception as e:
        print(str(e))
        pass

    pattern = r'\b\w+\.\w+\.\w+\b'
    article = re.sub(pattern, '', article)
    pattern = r"https:\/\/[A-Za-z0-9.-]+\/[A-Za-z0-9.-]+"
    article = re.sub(pattern, '', article)

    # 금지단어 체크~

    article = article.replace("있다.","있습니다.")
    article = article.replace("했다.","했습니다.")
    article = article.replace("이다.","입니다.")
    article = article.replace("았다.","았습니다.")
    article = article.replace("밀렸다.","밀렸습니다.")
    article = article.replace("내줬다.","내줬습니다.")
    article = article.replace("제쳤다.","제쳤습니다.")
    article = article.replace("앞질렀다.","앞질렀습니다.")
    article = article.replace("된다.","됩니다.")
    article = article.replace("됐다.","됐습니다.")
    article = article.replace("밝혔다.","밝혔습니다.")
    article = article.replace("하다.","합니다.")
    article = article.replace("나왔다.","나왔습니다.")
    article = article.replace("나왔다.","나왔습니다.")
    article = article.replace("탔다.","탔습니다.")
    article = article.replace("팔렸다.","팔렸습니다.")
    article = article.replace("었다.","었습니다.")
    article = article.replace("섰다.","섰습니다.")
    article = article.replace("랐다.","랐습니다.")
    article = article.replace("렸다.","렸습니다.")
    article = article.replace("사다.","사입니다.")
    article = article.replace("힌다.","힙니다.")
    article = article.replace("트다.","트입니다.")
    article = article.replace("하려면","하기 위해선.")
    article = article.replace("있었지만","있었다.")
    article = article.replace("덩달아","함께")
    article = article.replace("나타냈다.","나타냈습니다.")
    article = article.replace("졌다.","졌습니다.")
    article = article.replace("였다.","였습니다.")
    article = article.replace("한다.","합니다.")
    article = article.replace("갔다.","갔습니다.")
    article = article.replace("않다.","않습니다.")
    article = article.replace("없다.","없습니다.")
    article = article.replace("켰다.","켰습니다.")
    article = article.replace("냈다.","냈습니다.")
    article = article.replace("났다.","났습니다.")
    article = article.replace("줬다.","줬습니다.")
    article = article.replace("웠다.","웠습니다.")
    article = article.replace("친다.","칩니다.")
    article = article.replace("나간다.","나갑니다.")
    article = article.replace("높인다.","높입니다.")
    article = article.replace("쳤다.","쳤습니다.")
    article = article.replace("나온다.","나옵니다.")
    article = article.replace("렀다.","렀습니다.")
    article = article.replace("겼다.","겼습니다.")
    article = article.replace("이유다.","이유입니다.")
    article = article.replace("즈다.","즈입니다.")
    article = article.replace("왔다.","왔습니다.")
    article = article.replace("진다.","집니다.")
    article = article.replace("겁다.","겁습니다.")
    article = article.replace("수다.","수입니다.")
    article = article.replace("아니다.","아닙니다.")

    article = article.replace("사진=","")
    

    article = article.replace("린다.","립니다.")
    article = article.replace("있어서다.","있어서입니다.")
    article = article.replace("같다.","같습니다.")

    
    article = article.replace('"','')
    article = article.replace("△","")
    article = article.replace("▲","")
    article = article.replace("●","")
    article = article.replace("amp;","")
    article = article.replace("《","")
    article = article.replace("》","")
    article = article.replace("━","")
    article = article.replace("◆","")
    article = article.replace("◇","")
    article = article.replace("▶","")
    
    article = article.replace("■","")
    article = article.replace(">","")
    article = article.replace(":","")
    article = article.replace("※","")
    article = article.replace("―","")
    

    article = article.replace("  "," ")
    article = article.replace("  "," ")
    article = article.replace("  "," ")
    article = article.replace("  "," ")
    return article


def clean_text(input_string):
    # 정규 표현식 패턴을 사용하여 특수 문자 제거
    pattern = r'[^\w\s.]'
    clean_string = re.sub(pattern, '', input_string)

    # 링크 제거
    clean_string = re.sub(r'http\S+', '', clean_string)

    # 두 칸 이상의 공백을 하나의 공백으로 대체
    clean_string = re.sub(r'\s{2,}', ' ', clean_string)

    # 두 개 이상의 점을 하나로 대체
    clean_string = re.sub(r'\.{2,}', '.', clean_string)

    clean_string = re.sub(r'[a-zA-Z]+\.com', '', clean_string)

    # 문자열 양쪽의 공백 제거
    clean_string = clean_string.strip()

    return clean_string


# def articleModifyFin(article, workLink):

#     articleArr = article.split('.')
#     print(f"articleArr 갯수는??? : {len(articleArr)}")

#     if len(articleArr) < 500:
#         setNum = len(articleArr) // 5
#     elif len(articleArr) < 600:
#         setNum = len(articleArr) // 6
#     elif len(articleArr) < 700:
#         setNum = len(articleArr) // 7
#     elif len(articleArr) < 800:
#         setNum = len(articleArr) // 8
#     elif len(articleArr) < 900:
#         setNum = len(articleArr) // 9
#     else:
#         setNum = len(articleArr) // 3


#     try:
#         ranNum = random.randrange(3, len(articleArr) - 2)
#     except:
#         ranNum = len(articleArr) // 2

#     insertLinkTag = f"<a href='{workLink['tg_link']}' target='_blank'>{workLink['tg_keyword']}</a>"

#     articleArr
#     articleResult = ""
#     for idx, articleDiv in enumerate(articleArr):
#         articleDiv = articleDiv.strip()
#         if not (articleDiv.isalpha() or articleDiv.isdigit() or articleDiv.isspace() or ""):
#             articleResult = articleResult + articleDiv + ". "
        
#         if idx % setNum == 0:
#             articleResult = articleResult + "<br>"
        
#         if idx == ranNum:
#             articleResult = articleResult + " " + insertLinkTag + " "

#     articleResult = articleResult.replace(". .",".")
#     return articleResult



def insert_randomly(article, insertArr):
    article = clean_text(article)
    article = replaceText(article)
    array = article.split('.')
    array_len = len(array)
    insert_len = len(insertArr)
    if array_len < 3 or insert_len == 0:
        return array  # 배열 길이가 너무 짧거나 삽입할 요소가 없으면 그대로 반환

    possible_indices = list(range(1, array_len)) # 처음과 끝은 제외

    if len(possible_indices) < insert_len:
        return "배열 길이가 짧아 모든 요소를 삽입할 수 없습니다."

    random_indices = random.sample(possible_indices, insert_len)
    random_indices.sort() # 오름차순 정렬하여 삽입 시 인덱스 변화를 고려하기 쉽게 함

    # 인덱스 차이가 2 이상인지 확인하고, 아니면 다시 뽑기
    while True:
        valid = True
        for i in range(insert_len - 1):
            if random_indices[i+1] - random_indices[i] < 2:
                valid = False
                break
        if valid:
            break
        random_indices = random.sample(possible_indices, insert_len)
        random_indices.sort()

    new_array = list(array) # 원본 배열 복사
    offset = 0
    for i in range(insert_len):
        index_to_insert = random_indices[i] + offset
        new_array.insert(index_to_insert, insertArr[i])
        offset += 1

    formatStr = group_and_join_with_br(new_array)
    
    return formatStr



def group_and_join_with_br(array):
    result = []
    start_index = 0
    array_len = len(array)

    while start_index < array_len:
        group_size = random.choice([3, 5])
        end_index = min(start_index + group_size, array_len)
        group = array[start_index:end_index]
        result.append(" ".join(group))
        start_index = end_index

    # 마지막 요소를 제외하고 <br> 태그 추가
    formatted_result = ""
    for i in range(len(result) - 1):
        formatted_result += result[i] + "<br>\n"

    # 마지막 요소는 그대로 추가
    if result:
        formatted_result += result[-1]

    return formatted_result


def process_array(data, dataStr, type = "free"):
    # 1. 배열을 랜덤하게 섞기
    random.shuffle(data)
    
    # 2. cw_work_count 값에 따라 정렬하기 (작은 순서)
    sorted_data = sorted(data, key=lambda x: x[dataStr])
    
    if type == "free":
        maxNum = len(sorted_data)
        ranNum = 0
        if maxNum > 15:
            ranNum = random.randrange(13,16)
        else:
            result = math.ceil(maxNum / 2)
            ranNum = random.randrange(result,maxNum)
        # 3. 상위 15개 항목 추출
        topValue = sorted_data[:ranNum]
    else:
        topValue = sorted_data[0]

    return topValue

def wait_float(start, end):
    wait_ran = random.uniform(start, end)
    time.sleep(wait_ran)


def focus_window(winNames):
    while True:
        try:
            user32 = ctypes.windll.user32
            foreground_window = user32.GetForegroundWindow()
            window = gw.Window(foreground_window)
            chkDriver = False

            for winName in winNames:
                if winName in window.title:
                    chkDriver = True
                    break
                else:
                    windows = Desktop(backend="uia").windows()
                    for window in windows:
                        if winName in window.window_text():
                            window.set_focus()
                            break
            if chkDriver == True:
                break

        except Exception as e:
            print(str(e))
            pass