from wxauto4 import uia
from wxauto4.param import PROJECT_NAME
from wxauto4.logger import wxlog
from wxauto4.utils.lock import uilock
from abc import ABC, abstractmethod
import win32gui
import ctypes
from typing import Union
import time

class BaseUIWnd(ABC):
    _ui_cls_name: str = None
    _ui_name: str = None
    control: uia.Control

    @abstractmethod
    def _lang(self, text: str):pass

    def __repr__(self):
        return f"<{PROJECT_NAME} - {self.__class__.__name__} at {hex(id(self))}>"
    
    def __eq__(self, other):
        return self.control == other.control
    
    def __bool__(self):
        return self.exists()

    def _show(self):
        if not hasattr(self, 'HWND'):
            self.HWND = self.control.GetTopLevelControl().NativeWindowHandle
        
        # 检查窗口是否已经在前台
        try:
            from wxauto4.utils.win32 import is_window_visible
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == self.HWND and is_window_visible(self.HWND):
                return
        except:
            pass
        
        win32gui.ShowWindow(self.HWND, 1)
        win32gui.SetWindowPos(self.HWND, -1, 0, 0, 0, 0, 3)
        win32gui.SetWindowPos(self.HWND, -2, 0, 0, 0, 0, 3)
        self.control.Show()
        
        # 将窗口移到屏幕中央
        try:
            if hasattr(self.control, 'MoveToCenter') and self.control.IsTopLevel():
                self.control.MoveToCenter()
            else:
                rect = win32gui.GetWindowRect(self.HWND)
                window_width = rect[2] - rect[0]
                window_height = rect[3] - rect[1]
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                win32gui.SetWindowPos(self.HWND, 0, x, y, 0, 0, 0x0001)
        except:
            pass

    @property
    def pid(self):
        return self.control.ProcessId

    @uilock
    def close(self):
        try:
            for i in range(2):
                self.control.SendKeys('{Esc}')
        except:
            pass

    def exists(self, wait=0):
        try:
            result = self.control.Exists(wait)
            return result
        except:
            return False

class BaseUISubWnd(BaseUIWnd):
    root: BaseUIWnd
    parent: None

    def _lang(self, text: str):
        if getattr(self, 'parent'):
            return self.parent._lang(text)
        else:
            return self.root._lang(text)
