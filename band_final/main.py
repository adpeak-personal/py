from ongo import *



def goScriptAct():
    # getDict = {'ipval': ipVal.get(), 'gonggamVal': gonggamVal.get(), 'writeVal': writeVal.get(), 'neighborVal': neighborVal.get(), 'middleVal': middleVal.get()}
    # getDict['nlist'] = idbox.current() + 1
    onth = threading.Thread(target=lambda: goScript())
    
    onth.daemon = True
    onth.start()

def goStartCapture():
    onth = threading.Thread(target=lambda: goScriptCaptureWhile())
    
    onth.daemon = True
    onth.start()

root = Tk()
root.title("밴드 자동화")
root.geometry("300x100+500+300")
root.resizable(False, FALSE)


frame0 = LabelFrame(root, text='밴드 메인', padx=60, pady=10)  # padx / pady 내부여백
frame0.pack(padx=10, pady=5)  # padx / pady 외부여백

btn1 = Button(frame0, text='시작하기', command=goScriptAct, padx=50)
btn1.pack()

btn2 = Button(frame0, text='캡챠정리', command=goStartCapture, padx=50)
btn2.pack()

# 윈도우창 계속 띄우기
root.mainloop()
