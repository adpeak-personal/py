from ongo import *



def goScriptTraffic():
    getDict = {'ipval': ipVal.get(), 'group_val': groupVal.get(), 'workTypeVal': radVar.get()}
    onth = threading.Thread(target=lambda: trfficScript(getDict))
    
    onth.daemon = True
    onth.start()



root = Tk()
root.title("트래픽 프로그램")
root.geometry("300x230+500+300")
root.resizable(False, FALSE)


frame0 = LabelFrame(root, text='트래픽 프로그램', padx=60, pady=10)  # padx / pady 내부여백
frame0.pack(padx=10, pady=5)  # padx / pady 외부여백

radVar = StringVar()
ipVal = IntVar()
ipChk=Checkbutton(frame0,text="아이피 변경",variable=ipVal)
ipChk.select()
ipChk.pack()


groupVal = ttk.Entry(frame0, width=20, textvariable=str)
groupVal.pack()



# addWorkCount = ttk.Entry(frame0, width=20, textvariable=str)
# addWorkCount.pack()

radVar = tk.StringVar(value='mix')  # 기본값을 'mix'로 설정

action = Radiobutton(frame0, text = "PC 검색", variable=radVar, value = 'pc')  
action.pack()
action2 = Radiobutton(frame0, text = "모바일 검색", variable=radVar, value = 'mobile')  
action2.pack()
action3 = Radiobutton(frame0, text = "섞어서", variable=radVar, value = 'mix')  
action3.pack()


btn1 = Button(frame0, text='트래픽 프로그램!', command=goScriptTraffic, padx=50)
btn1.pack()



# 윈도우창 계속 띄우기
root.mainloop()
