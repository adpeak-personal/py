from ongo import *



def th():
    getDict = {'ipval': ipVal.get(), 'loginChkVal' : loginChkVal.get(), 'actVal' : actVal.get(), 'saveChkVal' : saveChkVal.get(), 'linkTwoChkVal' : linkTwoChkVal.get()}
    # getDict['nlist'] = idbox.current() + 1
    onth = threading.Thread(target=lambda: goScript(getDict))
    
    onth.daemon = True
    onth.start()

    
# def th2():
    
#     onth = threading.Thread(target=lambda: getLinkAndSubject())
#     onth.daemon = True
#     onth.start()
    


    
    
# 윈도우 창 생성 및 버튼 화면 조절
root = Tk()
root.title("블로그 자동화")
root.geometry("350x250+500+300")
root.resizable(False, FALSE)



frame0 = LabelFrame(root, text='체크항목')  # padx / pady 내부여백
frame0.pack(padx=10, pady=5)  # padx / pady 외부여백

ipVal = IntVar()
ipChk=Checkbutton(frame0,text="아이피 변경",variable=ipVal)
ipChk.select()
ipChk.grid(column=1, row=1)

 
loginChkVal = IntVar()
loginChkBox = Checkbutton(frame0,text="ID CHK",variable=loginChkVal)
loginChkBox.grid(column=1, row=2)

saveChkVal = IntVar()
saveChkBox = Checkbutton(frame0,text="Boho Chk",variable=saveChkVal)
saveChkBox.grid(column=2, row=2)

linkTwoChkVal = IntVar()
linkTwoChkBox = Checkbutton(frame0,text="2link",variable=linkTwoChkVal)
linkTwoChkBox.grid(column=3, row=2)
linkTwoChkBox.select()

actVal = StringVar()
action1 = Radiobutton(frame0, text="확인만", value='onlychk', variable=actVal)
action1.grid(column=1, row=3, sticky="nsew")


action3 = Radiobutton(frame0, text="체크", value='chk', variable=actVal)
action3.grid(column=2, row=3)  # 다른 행에 배치






frame1 = LabelFrame(root, text='아이디 선택', padx=60, pady=10)  # padx / pady 내부여백
frame1.pack(padx=10, pady=5)  # padx / pady 외부여백

# wb = load_workbook('./etc/nid.xlsx')
# ex = wb.active


# nid_list = []
# nlogin_list = []
# i = 0
# while True:
#     i += 1
#     id_val = ex.cell(i, 1).value
#     if id_val is None:
#         break
#     else:
#         nid_list.append(id_val)
        
# idbox = ttk.Combobox(frame1, values=nid_list)
# idbox.current(0)
# idbox.pack()

# textbox = ttk.Entry(frame1, width=20, textvariable=str)
# textbox.pack()



frame2 = LabelFrame(root, text='버튼', padx=60, pady=10)  # padx / pady 내부여백
frame2.pack(padx=10, pady=5)  # padx / pady 외부여백

# 시작 버튼 생성
btn1 = Button(frame2, text='시작하기', command=th, padx=50)
btn1.pack()



# btn3= Button(frame2, text='링크/제목 따기', command=th2, padx=50)
# btn3.pack()









# ********************************

# 윈도우창 계속 띄우기
root.mainloop()
