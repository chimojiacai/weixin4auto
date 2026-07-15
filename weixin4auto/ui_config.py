"""微信4.1版本的UI配置类名和AutomationId定义

注意：如果某些UI类名在微信4.1中不匹配，可能需要根据实际环境调整。
可以使用UI自动化工具（如Inspect.exe）检查实际的类名和AutomationId。
"""

class WxUI41Config:
    """微信4.1版本的UI类名配置
    
    如果遇到窗口或控件找不到的问题，请检查：
    1. 窗口类名是否正确（可以使用spy++或Inspect工具查看）
    2. UI类名是否匹配（mmui::前缀的类名）
    3. AutomationId是否变化
    """
    
    # 窗口类名（Qt框架窗口类名）
    # 注意：如果 'Qt51514QWindowIcon' 不匹配，可以尝试：
    # - 'Qt6QWindowIcon' (Qt 6)
    # - 'Qt6xxxQWindowIcon' (其他Qt6版本)
    # - 使用 find_wechat_window.py 或 spy++ 工具查看实际的窗口类名
    WIN_CLS_NAME = 'Qt51514QWindowIcon'  # 微信4.1实际使用的窗口类名
    
    # 主窗口UI类名
    MAIN_WINDOW_UI_CLS = 'mmui::MainWindow'
    
    # 子窗口UI类名
    SUB_WINDOW_UI_CLS = 'mmui::FramelessMainWindow'
    
    # 导航栏
    NAVIGATION_BAR_CLS = 'mmui::MainTabBar'
    NAVIGATION_BAR_AUTOMATION_ID = 'main_tabbar'
    
    # 会话列表
    SESSION_BOX_CLS = 'mmui::ChatMasterView'
    SESSION_LIST_CLS = 'mmui::ChatSessionList'
    SESSION_TABLE_CLS = 'mmui::XTableView'
    SESSION_SEARCH_FIELD_CLS = 'mmui::XSearchField'
    SESSION_SEARCH_CONTENT_CLS = 'mmui::SearchContentPopover'
    
    # 聊天页面
    CHAT_PAGE_CLS = 'mmui::ChatMessagePage'
    CHAT_SPLITTER_CLS = 'mmui::XSplitterView'
    CHAT_MESSAGE_VIEW_CLS = 'mmui::MessageView'
    CHAT_INPUT_FIELD_CLS = 'mmui::ChatInputField'
    CHAT_INFO_VIEW_CLS = 'mmui::ChatInfoView'
    
    # 消息类型
    MSG_BUBBLE_ITEM_CLS = 'mmui::ChatBubbleItemView'
    MSG_TEXT_ITEM_CLS = 'mmui::ChatTextItemView'
    MSG_VOICE_ITEM_CLS = 'mmui::ChatVoiceItemView'
    MSG_CARD_ITEM_CLS = 'mmui::ChatPersonalCardItemView'
    MSG_REFER_ITEM_CLS = 'mmui::ChatBubbleReferItemView'  # 动画表情、引用消息等
    
    # 组件
    MENU_CLS = 'mmui::XMenu'
    # 菜单窗口类名，如果不对可以尝试：
    # - 'Qt6xxxQWindowToolSaveBits' (其他Qt6版本)
    MENU_WIN_CLS = 'Qt51514QWindowToolSaveBits'  # 微信4.1实际使用的菜单窗口类名
    AT_MENU_CLS = 'mmui::XPopover'
    AT_MENU_AUTOMATION_ID = 'MentionPopover'
    UPDATE_WINDOW_CLS = 'mmui::XView'
    SESSION_PICKER_CLS = 'mmui::SessionPickerWindow'
    
    # 按钮类名
    BUTTON_OUTLINE_CLS = 'mmui::XOutlineButton'
    
    # 编辑框类名
    EDIT_VALIDATOR_CLS = 'mmui::XValidatorTextEdit'
    
    # 其他
    PREVIEW_TOOLBAR_CLS = 'mmui::PreviewToolbarView'
    PLAYER_CONTROL_CLS = 'mmui::XPlayerControlView'
    
    # 用户信息弹窗
    CONTACT_HEAD_VIEW_CLS = 'mmui::ContactHeadView'
    CONTACT_HEAD_VIEW_AUTOMATION_ID = 'head_image_v_view.head_view_'

