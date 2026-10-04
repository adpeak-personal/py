from func import *


def goScript(getDict):


    
    
    import time

    # 크롬을 실행하고 약간 기다린다
    time.sleep(2)  # 이미 실행되어 있다면 이건 생략 가능

    # 모든 창 이름 가져오기
    windows = gw.getWindowsWithTitle('네이버 블로그')

    # 크롬 창이 있다면
    for win in windows:
        if win.title != '' and '네이버 블로그' in win.title:
            # 창을 복원하고 포커스
            win.restore()
            win.activate()

            # 위치와 크기 조정 (x, y, width, height)
            win.moveTo(0, 0)      # 위치: 왼쪽에서 100px, 위에서 100px
            win.resizeTo(1200, 900)   # 크기: 가로 1280, 세로 800
            break

    file_path = f"./content/content.txt"
    if os.path.isfile(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

    print(lines)
    lineCount = -1
    while True:
        try:
            lineCount += 1
            getline = lines[lineCount].replace('\n','')

            chkAction = getline.split('|')

            pg.moveTo(600, 820)
            pg.leftClick()
            wait_float(0.3,0.9)


            if getline is None:
                pg.alert('작성 완료!!')
                sys.exit(0)
            elif lineCount == 0:
                pg.moveTo(600, 370)
                pg.leftClick()
                keyboard.write(text=getline, delay=0.07)
                wait_float(1.2,2.8)
            elif chkAction[0] == 'img_line':
                nowPath = os.getcwd()

                while True:
                    pg.moveTo(45,195)
                    pg.leftClick()

                    imagePath = nowPath + f"\content"
                    wait_float(1.5, 2.2)
                    pyperclip.copy(imagePath)
                    wait_float(0.5, 0.9)
                    pg.hotkey('ctrl','v')
                    wait_float(0.5, 0.9)
                    pg.press('enter')
                    
                    wait_float(0.9, 1.6)
                    pyperclip.copy(chkAction[1])
                    wait_float(0.5, 0.9)
                    pg.hotkey('ctrl','v')
                    wait_float(0.5, 0.9)
                    pg.press('enter')
                    wait_float(3.5,4.5)
                    fileInputWinBool = is_file_dialog_open()
                    if fileInputWinBool == False:
                        break
                    else:
                        pg.press('esc')
                        wait_float(2.5,3.5)
                continue
            elif getline == 'enter':
                pg.press('enter')
            elif getline == 'wait':
                pg.press('enter')
                wait_float(4.5,5.5)
                pg.press('enter')
            
            else:
                keyboard.write(text=getline, delay=0.07)
                wait_float(0.5,0.9)
                pg.press('enter')
                wait_float(0.5,0.9)
        except:
            break

    siteLink = "https://happy-toad2.shop"
    while True:
        try:
            res = requests.get(f"{siteLink}/api/v7/blog_aligo").json()
            if res['status']:
                break
        except Exception as e:
            print('에러요~~~')
            print(str(e))
            pass
        wait_float(1.2,2.5)

    for i in range(3):
        fr = 1600    # range : 37 ~ 32767
        du = 500     # 1000 ms ==1second
        sd.Beep(fr, du)
    pg.alert('작업완료~~')
        


def is_file_dialog_open():
    # 열려 있는 창 목록 확인
    for w in gw.getAllTitles():
        if '열기' in w or 'Open' in w:
            return True
    return False


def cleanUpImage():

    # 대상 폴더 경로
    folder_path = './content'
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')

    # 이미지 파일 리스트 추출
    image_files = [f for f in os.listdir(folder_path)
                if f.lower().endswith(image_extensions)]
    
    img_files_dict = {}

    for img in image_files:
        print(img)
        imgPrefix = img[:3]
        number = ''.join(re.findall(r'\d', imgPrefix))
        img_files_dict[number] = f"img_line|{img.split('.')[0]}"

    # 파일 읽기
    with open('./content/content.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped in img_files_dict:
            new_lines.append(img_files_dict[stripped])  # 숫자를 대응 이미지로 교체
        elif stripped == "" or stripped is None:
            new_lines.append('enter')
        else:
            new_lines.append(stripped)  # 그대로 유지

    # 결과 저장
    with open('./content/content.txt', 'w', encoding='utf-8') as f:
        for line in new_lines:
            f.write(line + '\n')
            
    pg.alert('완료!')