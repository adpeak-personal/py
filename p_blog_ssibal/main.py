from ongo import *



def th():
    getDict = {}
    # getDict['nlist'] = idbox.current() + 1
    onth = threading.Thread(target=lambda: goScript(getDict))
    
    onth.daemon = True
    onth.start()

    
def th2():
    
    onth = threading.Thread(target=lambda: cleanUpImage())
    onth.daemon = True
    onth.start()
    


    
    
# 윈도우 창 생성 및 버튼 화면 조절
root = Tk()
root.title("개인블로그 자동화")
root.geometry("350x140+500+300")
root.resizable(False, FALSE)


frame2 = LabelFrame(root, text='버튼', padx=60, pady=10)  # padx / pady 내부여백
frame2.pack(padx=10, pady=5)  # padx / pady 외부여백

# 시작 버튼 생성
btn1 = Button(frame2, text='시작하기', command=th, padx=50)
btn1.pack(pady=(0, 5))  # 아래쪽 간격 5px


# 시작 버튼 생성
btn2 = Button(frame2, text='이미지정리', command=th2, padx=50)
btn2.pack(pady=(5, 0))  # 위쪽 간격 5px









# ********************************

# 윈도우창 계속 띄우기
root.mainloop()
