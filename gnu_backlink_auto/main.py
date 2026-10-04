from ongo import *



def th():
    getDict = {'test_val' : testChkVal.get()}
    onth = threading.Thread(target=lambda: goScript(getDict))
    onth.daemon = True
    onth.start()


def th2():
    getDict = {}
    onth = threading.Thread(target=lambda: joinScript(getDict))
    onth.daemon = True
    onth.start()

    
# def th2():
    
#     onth = threading.Thread(target=lambda: getLinkAndSubject())
#     onth.daemon = True
#     onth.start()
    


    
    
# 윈도우 창 생성 및 버튼 화면 조절
root = Tk()
root.title("그누보드 자동화")
root.geometry("350x150+500+300")
root.resizable(False, FALSE)





frame0 = LabelFrame(root, text='버튼', padx=60, pady=10)  # padx / pady 내부여백
frame0.pack(padx=10, pady=5)  # padx / pady 외부여백


testChkVal = IntVar()
testChkBox = Checkbutton(frame0,text="테스트",variable=testChkVal)
testChkBox.pack()


# 시작 버튼 생성
btn1 = Button(frame0, text='작업 시작', command=th, padx=50)
btn1.pack()

# 시작 버튼 생성
btn2 = Button(frame0, text='회원 가입', command=th2, padx=50)
btn2.pack()



# btn3= Button(frame2, text='링크/제목 따기', command=th2, padx=50)
# btn3.pack()









# ********************************

# 윈도우창 계속 띄우기
root.mainloop()
