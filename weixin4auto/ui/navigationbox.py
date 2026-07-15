from weixin4auto import uia
from weixin4auto.param import (
    WxParam, 
    WxResponse,
)
from weixin4auto.utils.win32 import GetAllWindows
from weixin4auto.ui_config import WxUI41Config
from weixin4auto.logger import wxlog
import time

class NavigationBox:
    def __init__(self, control, parent):
        self.control: uia.Control = control
        self.root = parent.root
        self.parent = parent
        self.init()

    def init(self):
        self.my_icon = None
        
        if self.control is None:
            # 新版微信可能没有导航栏 ToolBar，所有图标设为 None
            self.chat_icon = None
            self.contact_icon = None
            self.favorites_icon = None
            self.files_icon = None
            self.moments_icon = None
            self.browser_icon = None
            self.video_icon = None
            self.stories_icon = None
            self.mini_program_icon = None
            self.phone_icon = None
            self.settings_icon = None
            return
        
        try:
            buttons = self.control.GetChildren()
            if buttons:
                self.my_icon = buttons[0]
        except:
            pass
        
        self.chat_icon = self.control.ButtonControl(Name=self._lang('微信'))
        self.contact_icon = self.control.ButtonControl(Name=self._lang('通讯录'))
        self.favorites_icon = self.control.ButtonControl(Name=self._lang('收藏'))
        self.files_icon = self.control.ButtonControl(Name=self._lang('聊天文件'))
        self.moments_icon = self.control.ButtonControl(Name=self._lang('朋友圈'))
        self.browser_icon = self.control.ButtonControl(Name=self._lang('搜一搜'))
        self.video_icon = self.control.ButtonControl(Name=self._lang('视频号'))
        self.stories_icon = self.control.ButtonControl(Name=self._lang('看一看'))
        self.mini_program_icon = self.control.ButtonControl(Name=self._lang('小程序面板'))
        self.phone_icon = self.control.ButtonControl(Name=self._lang('手机'))
        self.settings_icon = self.control.ButtonControl(Name=self._lang('更多'))
    
    def get_user_nickname(self) -> str:
        """获取当前登录者的昵称
        
        点击头像区域（"微信"按钮上方40px），获取弹出组件的name作为昵称
        
        Returns:
            str: 当前登录者的昵称，如果获取失败返回空字符串
        """
        try:
            self.parent._show()
            time.sleep(0.2)
            
            # 查找"微信"按钮：优先用导航栏的 chat_icon，否则从主窗口直接查找
            chat_button = None
            if self.chat_icon is not None:
                try:
                    if self.chat_icon.Exists(0.5):
                        chat_button = self.chat_icon
                except:
                    pass
            
            if chat_button is None:
                main_control = self.parent.control
                if main_control is not None:
                    try:
                        btn = main_control.ButtonControl(Name=self._lang('微信'))
                        if btn.Exists(1):
                            chat_button = btn
                    except:
                        pass
            
            if chat_button is None:
                return ""
            
            # 获取"微信"按钮的位置，在其上方40px处点击头像
            rect = chat_button.BoundingRectangle
            avatar_x = (rect.left + rect.right) // 2
            avatar_y = (rect.top + rect.bottom) // 2 - 40
            if avatar_y < 0:
                avatar_y = max(0, rect.top - 40)
            
            # 点击头像区域
            uia.Click(avatar_x, avatar_y)
            time.sleep(0.5)
            
            # 从弹窗窗口中查找昵称
            nickname = ""
            try:
                menu_cls = WxUI41Config.MENU_WIN_CLS
                
                # 尝试多种窗口名和类名组合
                all_wins = []
                for combo in [{'classname': menu_cls, 'name': 'Weixin'}, {'classname': menu_cls}]:
                    wins = GetAllWindows(**combo)
                    all_wins.extend(wins)
                
                # 去重
                seen_hwnds = set()
                unique_wins = []
                for w in all_wins:
                    if w[0] not in seen_hwnds:
                        seen_hwnds.add(w[0])
                        unique_wins.append(w)
                
                for win in unique_wins:
                    control = uia.ControlFromHandle(win[0])
                    if control.ClassName in ['mmui::ProfileUniquePop', 'mmui::XPopover', WxUI41Config.MENU_CLS]:
                        # 从弹窗中查找ContactHeadView控件
                        try:
                            head_view = control.ButtonControl(
                                ClassName=WxUI41Config.CONTACT_HEAD_VIEW_CLS,
                                AutomationId=WxUI41Config.CONTACT_HEAD_VIEW_AUTOMATION_ID
                            )
                            if head_view.Exists(1):
                                nickname = head_view.Name if hasattr(head_view, 'Name') else ""
                                if nickname:
                                    break
                        except:
                            pass
                        
                        # 如果直接查找失败，递归查找
                        if not nickname:
                            def find_in_popup(ctrl, depth=0, max_depth=5):
                                if depth > max_depth:
                                    return None
                                try:
                                    for child in ctrl.GetChildren():
                                        if (child.ControlTypeName == 'ButtonControl' and 
                                            getattr(child, 'ClassName', '') == WxUI41Config.CONTACT_HEAD_VIEW_CLS):
                                            child_name = getattr(child, 'Name', '')
                                            if child_name and child_name.strip():
                                                return child_name.strip()
                                        result = find_in_popup(child, depth + 1, max_depth)
                                        if result:
                                            return result
                                except:
                                    pass
                                return None
                            
                            nickname = find_in_popup(control)
                            if nickname:
                                break
            except:
                pass
            
            # 关闭弹出组件
            try:
                if chat_button:
                    chat_button.Click()
                    time.sleep(0.1)
            except:
                pass
            
            return nickname.strip() if nickname else ""
        except:
            try:
                if self.chat_icon:
                    self.chat_icon.Click()
            except:
                pass
            return ""

    def _lang(self, text):
        return text

    def switch_to_chat_page(self):
        if self.chat_icon: self.chat_icon.Click()

    def switch_to_contact_page(self):
        if self.contact_icon: self.contact_icon.Click()

    def switch_to_favorites_page(self):
        if self.favorites_icon: self.favorites_icon.Click()

    def switch_to_files_page(self):
        if self.files_icon: self.files_icon.Click()

    def switch_to_browser_page(self):
        if self.browser_icon: self.browser_icon.Click()

    def switch_to_moments_page(self):
        if self.moments_icon: self.moments_icon.Click()

    def switch_to_video_page(self):
        if self.video_icon: self.video_icon.Click()

    def switch_to_stories_page(self):
        if self.stories_icon: self.stories_icon.Click()

    def switch_to_mini_program_page(self):
        if self.mini_program_icon: self.mini_program_icon.Click()

    def switch_to_phone_page(self):
        if self.phone_icon: self.phone_icon.Click()

    def switch_to_settings_page(self):
        if self.settings_icon: self.settings_icon.Click()
