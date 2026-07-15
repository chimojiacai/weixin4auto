from __future__ import annotations
from wxauto4 import uia
from wxauto4.param import (
    WxParam,
    WxResponse,
)
from wxauto4.languages import MENU_OPTIONS
from wxauto4.ui.component import Menu
from wxauto4.utils.win32 import SetClipboardText
from wxauto4.logger import wxlog
from wxauto4.ui_config import WxUI41Config
import time
from typing import (
    Union,
    List
)
import re


class SessionBox:
    def __init__(self, control, parent):
        self.control: uia.Control = control
        self.root = parent.root
        self.parent = parent
        self.init()

    def init(self):
        self.searchbox = self.control.GroupControl(ClassName=WxUI41Config.SESSION_SEARCH_FIELD_CLS).EditControl()
        self.session_list = self.control.GroupControl(ClassName=WxUI41Config.SESSION_LIST_CLS).\
            ListControl(ClassName=WxUI41Config.SESSION_TABLE_CLS, Name="会话")
        self.search_content = self.parent.control.WindowControl(ClassName=WxUI41Config.SESSION_SEARCH_CONTENT_CLS)
        
    def roll_up(self, n: int=5):
        self.control.MiddleClick()
        self.control.WheelUp(wheelTimes=n)

    def roll_down(self, n: int=5):
        self.control.MiddleClick()
        self.control.WheelDown(wheelTimes=n)

    def get_session(self) -> List[SessionElement]:
        """获取会话列表
        
        如果找不到会话列表，会尝试多种方式定位
        """
        # 首先尝试标准方式
        if self.session_list.Exists(0):
            children = self.session_list.GetChildren()
            if children:
                return [SessionElement(i, self) for i in children]
        
        # 如果标准方式失败，尝试直接查找ListControl
        try:
            # 尝试在SessionBox中直接查找ListControl
            list_controls = []
            def find_list_controls(control, depth=0, max_depth=3):
                """递归查找ListControl"""
                if depth > max_depth:
                    return []
                results = []
                try:
                    if control.ControlTypeName == 'ListControl':
                        # 检查是否是会话列表（通常包含"会话"或有很多子元素）
                        children = control.GetChildren()
                        if len(children) > 0 or '会话' in (control.Name or ''):
                            results.append(control)
                    for child in control.GetChildren():
                        results.extend(find_list_controls(child, depth+1, max_depth))
                except:
                    pass
                return results
            
            list_controls = find_list_controls(self.control)
            
            # 优先使用名称包含"会话"的，或者子元素最多的
            if list_controls:
                list_controls.sort(key=lambda c: len(c.GetChildren()), reverse=True)
                target_list = list_controls[0]
                children = target_list.GetChildren()
                if children:
                    # 更新session_list引用
                    self.session_list = target_list
                    return [SessionElement(i, self) for i in children]
        except:
            pass
        
        return []

    def find_session_in_current_view(
            self, 
            keywords: str, 
            exact: bool = False
        ) -> Union[SessionElement, None]:
        """在当前可见的会话列表中查找匹配的会话（不滚动）
        
        Args:
            keywords: 要查找的会话名称关键词
            exact: 是否精确匹配，默认False（模糊匹配）
            
        Returns:
            SessionElement: 找到的会话元素，如果未找到返回None
        """
        try:
            # 获取当前可见的会话列表（不滚动）
            sessions = self.get_session()
            if not sessions:
                return None
            
            # 只查找当前可见的会话（在窗口内的）
            visible_sessions = [
                session for session in sessions 
                if uia.IsElementInWindow(self.session_list, session.control)
            ]
            
            if not visible_sessions:
                return None
            
            # 清理关键词
            clean_keywords = keywords.split('?')[0].split('，')[0].split(',')[0].strip()
            
            def extract_name(full_name: str) -> str:
                """提取名称的第一部分（第一个空格之前）"""
                if not full_name:
                    return ""
                first_space_idx = full_name.find(' ')
                return full_name[:first_space_idx].strip() if first_space_idx > 0 else full_name.strip()
            
            # 查找匹配的会话
            for session in visible_sessions:
                extracted_name = extract_name(session.name)
                
                if exact:
                    # 精确匹配
                    if (extracted_name == clean_keywords or 
                        extracted_name == keywords or
                        session.name == clean_keywords or 
                        session.name == keywords):
                        return session
                else:
                    # 模糊匹配
                    if (clean_keywords in extracted_name or 
                        keywords in extracted_name or
                        clean_keywords in session.name or 
                        keywords in session.name):
                        return session
            
            return None
        except:
            return None

    def search(
            self, 
            keywords: str,
            force: bool = False,
            force_wait: Union[float, int] = 0.5
        ):
        """搜索会话
        
        Args:
            keywords: 搜索关键词
            force: 是否强制搜索（等待固定时间）
            force_wait: 强制搜索等待时间
        """
        try:
            if not self.searchbox.Exists(0.5):
                return []
            
            self.searchbox.Click()
            time.sleep(0.1)
            self.searchbox.SendKeys('{Ctrl}a')  # 全选
            time.sleep(0.1)
            
            # 设置剪贴板并粘贴
            SetClipboardText(keywords)
            time.sleep(0.1)
            
            # 尝试多种粘贴方式
            try:
                self.searchbox.SendKeys('{Ctrl}v')
                time.sleep(0.2)
            except:
                try:
                    self.searchbox.RightClick()
                    time.sleep(0.2)
                    menu = Menu(self)
                    if menu.exists(0.5):
                        menu.select('粘贴')
                        time.sleep(0.2)
                except:
                    pass
            
            # 触发搜索（点击搜索框外部或按回车）
            self.searchbox.MiddleClick()
            time.sleep(0.3)  # 等待搜索结果出现

            if force:
                time.sleep(force_wait)

            try:
                if not self.search_content.Exists(1):
                    return []
                
                search_result = self.search_content.ListControl()
                if not search_result.Exists(0.5):
                    return []
                
                children = search_result.GetChildren()
                return [SearchResultElement(i) for i in children]
            except:
                return []
                
        except:
            return []
    
    def _close_search(self):
        """关闭搜索面板并清空搜索框"""
        try:
            # 按 Escape 关闭搜索面板
            self.control.SendKeys('{Escape}')
            time.sleep(0.1)
        except:
            pass
        try:
            # 如果搜索面板还在，点击空白区域关闭
            if self.search_content.Exists(0):
                self.control.MiddleClick()
                time.sleep(0.1)
        except:
            pass

    def switch_chat(
        self,
        keywords: str, 
        exact: bool = True,
        force: bool = False,
        force_wait: Union[float, int] = 0.5
    ):
        clean_keywords = keywords.split('?')[0].split('，')[0].split(',')[0].strip()
        try:
            # 执行搜索
            search_result = self.search(clean_keywords, force, force_wait)
            
            t0 = time.time()
            max_wait = min(WxParam.SEARCH_CHAT_TIMEOUT, 3)
            while not self.search_content.Exists(0.5) and (time.time() - t0) < max_wait:
                time.sleep(0.1)
            
            if not self.search_content.Exists(0):
                return None
            
            try:
                search_box = self.search_content.ListControl()
                if not search_box.Exists(1):
                    self._close_search()
                    return None
            except:
                self._close_search()
                return None
            
            t0 = time.time()
            search_result_items = []
            while (time.time() - t0) < max_wait:
                try:
                    search_result_items = search_box.GetChildren()
                    if search_result_items:
                        break
                    time.sleep(0.1)
                except:
                    time.sleep(0.1)
            
            if not search_result_items:
                self._close_search()
                return None
            
            matched_items = []
            current_section = 'contact'  # 默认为联系人（新版微信可能没有分类头）
            
            # 分类头关键词（用于识别分区标题）
            section_headers = {
                '联系人': 'contact',
                '群聊': 'group',
                '聊天记录': 'chat_history',
                '功能': 'function',
            }
            
            for search_result_item in search_result_items:
                try:
                    text: str = search_result_item.Name
                    if not text:
                        continue
                    
                    # 优先检查分区头（必须在 skip_keywords 之前，否则"搜索网络结果"会被跳过而不更新分区）
                    if text in section_headers:
                        current_section = section_headers[text]
                        continue
                    elif '搜索网络结果' in text or '网络' in text:
                        current_section = None
                        continue
                    
                    # 跳过非联系人项
                    skip_keywords = ['搜索建议', '查看更多']
                    if any(keyword in text for keyword in skip_keywords):
                        continue
                    
                    main_text = text.split('\n')[0].split('包含:')[0].strip()
                    is_match = False
                    match_text = main_text
                    
                    if exact:
                        if main_text == clean_keywords or main_text == keywords:
                            is_match = True
                        elif text == clean_keywords or text == keywords:
                            is_match = True
                            match_text = text
                        elif (
                            ' 微信号: ' in text
                            and (split:=text.split(' 微信号: '))[-1].lower() == clean_keywords.lower()
                        ):
                            is_match = True
                            match_text = split[0]
                        elif (
                            ' 昵称: ' in text
                            and (split:=text.split(' 昵称: '))[-1].lower() == clean_keywords.lower()
                        ):
                            is_match = True
                            match_text = split[0]
                    else:
                        if clean_keywords in main_text or keywords in main_text:
                            is_match = True
                        elif clean_keywords in text or keywords in text:
                            is_match = True
                            match_text = main_text if main_text else text
                    
                    # 只匹配联系人/群聊/功能类型的结果（None表示网络搜索区域，不匹配）
                    if is_match and current_section in ['contact', 'group', 'function']:
                        item_type = current_section if current_section in ['contact', 'group'] else 'contact'
                        matched_items.append({
                            'item': search_result_item,
                            'text': match_text,
                            'type': item_type,
                            'full_text': text
                        })
                        
                except:
                    continue
            
            if not matched_items:
                self._close_search()
                return None
            
            type_priority = {'contact': 0, 'group': 1}
            matched_items.sort(key=lambda x: type_priority.get(x['type'], 99))
            selected = matched_items[0]
            
            try:
                selected['item'].Click()
                time.sleep(0.2)
                return selected['text']
            except:
                self._close_search()
                return None
            
        except:
            self._close_search()
            return None

    def open_separate_window(self, name: str):
        """打开独立窗口"""
        realname = self.switch_chat(name)
        if not realname:
            return WxResponse.failure('未找到会话')
        
        time.sleep(0.1)
        
        try:
            sessions = [i for i in self.get_session() if uia.IsElementInWindow(self.session_list, i.control)]
            if not sessions:
                return WxResponse.failure('未找到会话列表')
            
            target_session = None
            for session in sessions:
                if session.content.startswith(realname):
                    target_session = session
                    break
            
            if not target_session:
                return WxResponse.failure(f'未找到会话: {realname}')
            
            target_session.double_click()
            time.sleep(0.2)
            return WxResponse.success(data={'nickname': realname})
        except:
            return WxResponse.failure('打开独立窗口失败')


    def go_top(self):
        self.control.MiddleClick()
        self.control.SendKeys('{Home}')

    def go_bottom(self):
        self.control.MiddleClick()
        self.control.SendKeys('{End}')
    
class SessionElement:
    def __init__(
            self, 
            control: uia.Control, 
            parent: SessionBox, 
        ):
        self.root = parent.root
        self.parent = parent
        self.control = control
        self.content = control.Name

    @property
    def texts(self) -> List[str]:
        """拆分当前会话控件中的文本行"""

        return [
            line for line in str(self.content).split('\n')
            if line and line.strip()
        ]

    @property
    def name(self) -> str:
        """会话名称"""

        if self.texts:
            return self.texts[0]
        return ''

    @property
    def unread_count(self) -> int:
        """未读消息数量"""

        unread_pattern = re.compile(r'\[(\d+)条\]')
        for text in self.texts:
            if match := unread_pattern.search(text):
                return int(match.group(1))
        return 0

    def _menu_option_text(self, option_key: str) -> str:
        option = MENU_OPTIONS.get(option_key, {})
        lang = getattr(WxParam, 'LANGUAGE', 'cn')
        text = option.get(lang) if isinstance(option, dict) else None
        if not text:
            text = option.get('cn') if isinstance(option, dict) else None
        return text or option_key

    def select_menu_option(self, option_key: str, wait=0.3):
        """根据配置语言选择菜单项"""

        option_text = self._menu_option_text(option_key)
        return self.select_option(option_text, wait)

    def __repr__(self):
        content = str(self.content).replace('\n', ' ')
        if len(content) > 5:
            content = content[:5] + '...'
        return f"<wxauto4 Session Element({content})>"
    
    def roll_into_view(self):
        uia.RollIntoView(self.control.GetParentControl(), self.control)

    # @uilock
    def _click(self, right: bool=False, double: bool=False):
        self.roll_into_view()
        if right:
            self.control.RightClick()
        elif double:
            self.control.DoubleClick()
        else:
            self.control.Click()

    def click(self):
        self._click()

    def right_click(self):
        self._click(right=True)

    def double_click(self):
        self._click()
        self._click(double=True)

    def select_option(self, option: str, wait=0.3):
        self.roll_into_view()
        self.control.RightClick()
        time.sleep(wait)
        menu = Menu(self.parent)
        return menu.select(option)

    def pin(self):
        """置顶聊天"""

        return self.select_menu_option('置顶')

    def unpin(self):
        """取消置顶聊天"""

        return self.select_menu_option('取消置顶')

    def mark_unread(self):
        """标记为未读"""

        return self.select_menu_option('标为未读')

    def toggle_mute(self):
        """切换消息免打扰状态"""

        return self.select_menu_option('消息免打扰')

    def open_in_separate_window(self):
        """在独立窗口中打开会话"""

        return self.select_menu_option('在独立窗口打开')

    def hide(self):
        """不显示聊天"""

        return self.select_menu_option('不显示聊天')

    def delete(self):
        """删除聊天"""

        return self.select_menu_option('删除聊天')

class SearchResultElement:
    def __init__(self, control):
        self.control = control
        self.content = control.Name
        self.type = control.ClassName

    def __repr__(self):
        content = str(self.content).replace('\n', ' ')
        if len(content) > 5:
            content = content[:5] + '...'
        return f"<wxauto4 Search Element({content})>"

    def get_all_text(self):
        return [
            line for line in str(self.content).split('\n')
            if line and line.strip()
        ]
    
    def click(self):
        uia.RollIntoView(self.control.GetParentControl(), self.control)
        self.control.Click()

    def close(self):
        self.control.SendKeys('{Esc}')
