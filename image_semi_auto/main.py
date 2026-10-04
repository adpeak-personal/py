from ongo import *



def th():
    getDict = {'work_site' : workSite.get()}
    onth = threading.Thread(target=lambda: goScript(getDict))
    
    onth.daemon = True
    onth.start()

def th2():
    getDict = {'start_val' : startValue.get(), 'count_val' : countValue.get()}
    onth = threading.Thread(target=lambda: get_nidx_list(getDict))
    
    onth.daemon = True
    onth.start()

def th3():
    getDict = {'start_val' : startValue.get()}
    onth = threading.Thread(target=lambda: check_alive_blog(getDict))
    
    onth.daemon = True
    onth.start()


def th4():

    getDict = {'link_count' : linkCountValue.get()}

    
    onth = threading.Thread(target=lambda: get_latest_link(getDict))
    onth.daemon = True
    onth.start()


    
# 윈도우 창 생성 및 버튼 화면 조절
root = Tk()
root.title("이미지 다운 반자동!!!")
root.geometry("300x450+500+300")
root.resizable(False, FALSE)




frame1 = LabelFrame(root, text='이미지 다운 반자동', padx=60, pady=10)  # padx / pady 내부여백
frame1.pack(padx=10, pady=5)  # padx / pady 외부여백


workSite = StringVar()

action1 = Radiobutton(frame1, text="Naver", value='naver', variable=workSite)
action1.pack()

action2 = Radiobutton(frame1, text="Google", value='google', variable=workSite)
action2.pack()  # 다른 행에 배치

# 시작 버튼 생성
btn1 = Button(frame1, text='시작하기', command=th, padx=50)
btn1.pack()

frame1 = LabelFrame(root, text='이미지 다운 반자동', padx=60, pady=10)  # padx / pady 내부여백
frame1.pack(padx=10, pady=5)  # padx / pady 외부여백


frame2 = LabelFrame(root, text='idx 리스트 가져오기', padx=60, pady=10)  # padx / pady 내부여백
frame2.pack(padx=10, pady=2)  # padx / pady 외부여백

frame3 = LabelFrame(root, text='최신 글 링크 따기', padx=60, pady=10)  # padx / pady 내부여백
frame3.pack(padx=10, pady=2)  # padx / pady 외부여백

# 레이블 추가
label = ttk.Label(frame2, text="블로그 순서 시작 값 입력")
label.pack(pady=1)

# Ttk Entry (입력 창) 추가
startValue = ttk.Entry(frame2, width=20)  # 너비 30 설정
startValue.pack(padx=5)


# 레이블 추가
label = ttk.Label(frame2, text="이미지 따기 갯수 입력")
label.pack(pady=1)

# Ttk Entry (입력 창) 추가
countValue = ttk.Entry(frame2, width=20)  # 너비 30 설정
countValue.pack(padx=5)

# 시작 버튼 생성
btn2 = Button(frame2, text='idx 리스트', command=th2, padx=50)
btn2.pack()

# 시작 버튼 생성
btn3 = Button(frame2, text='블로그 체크', command=th3, padx=50)
btn3.pack()
# btn3= Button(frame2, text='링크/제목 따기', command=th2, padx=50)
# btn3.pack()


# 시작 버튼 생성

# 레이블 추가
label = ttk.Label(frame3, text="링크 따기 갯수 입력")
label.pack(pady=1)

# Ttk Entry (입력 창) 추가
linkCountValue = ttk.Entry(frame3, width=20)  # 너비 30 설정
linkCountValue.pack(padx=5)

getLinkBtn = Button(frame3, text='링크 따기!!', command=th4, padx=50)
getLinkBtn.pack()



# ********************************

# 윈도우창 계속 띄우기
root.mainloop()
