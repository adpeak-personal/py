import random
import threading
import time
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path
import requests
# from typing import Optional
# from pyparsing import And

# from bs4 import BeautifulSoup as bs
import json
import re
import pyautogui as pg
import pyperclip
import pygetwindow as gw
import ctypes
# from pywinauto import Desktop

# import clipboard as cb

import keyboard
from tkinter import *
from tkinter import ttk
import winsound as ws
import winsound as sd
import shutil
import getpass
import os


def wait_float(start, end):
    wait_ran = random.uniform(start, end)
    time.sleep(wait_ran)

def focus_window(winName):
    while True:
        try:
            user32 = ctypes.windll.user32
            foreground_window = user32.GetForegroundWindow()
            window = gw.Window(foreground_window)
            if winName in window.title:
                break
            else:
                windows = Desktop(backend="uia").windows()
                for window in windows:
                    if winName in window.window_text():
                        window.set_focus()
                        break
        except Exception as e:
            print(str(e))
            pass