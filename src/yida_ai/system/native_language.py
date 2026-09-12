from __future__ import annotations

import time

from yida_ai.adapters.captions.windows_native import WindowsTextReader

LANGUAGE_NAMES = {
    "zh-CN": ("Chinese (Simplified, China)", "中文(简体，中国)", "中文（简体，中国）",
              "Chinês (Simplificado, China)", "简体中文(中国大陆)",
              "Chinese (Simplified, Mainland China)"),
    "en-US": ("English (United States)", "英语(美国)", "英语（美国）",
              "Inglês (Estados Unidos)"),
    "pt-BR": ("Portuguese (Brazil)", "葡萄牙语(巴西)", "葡萄牙语（巴西）",
              "Português (Brasil)"),
}


def switch_caption_language(language: str) -> bool:
    """Invoke system controls on a worker. Never use global keyboard events."""
    if language not in LANGUAGE_NAMES:
        return False
    reader = WindowsTextReader()
    try:
        hwnd = reader.window_handle()
        if not hwnd:
            return False
        root = reader.automation.ElementFromHandle(hwnd)
        import comtypes.gen.UIAutomationClient as uia

        def invoke(element):
            element.GetCurrentPattern(10000).QueryInterface(uia.IUIAutomationInvokePattern).Invoke()

        def by_id(value):
            return root.FindFirst(4, reader.automation.CreatePropertyCondition(30011, value))

        dropdown = by_id("SpeechModelDropDown")
        if not dropdown:
            settings = by_id("SettingsButton")
            if not settings:
                return False
            invoke(settings)
            time.sleep(0.2)
            change = by_id("ChangeLanguageMenuFlyoutItem")
            if not change:
                return False
            invoke(change)
            time.sleep(0.2)
            dropdown = by_id("SpeechModelDropDown")
        if dropdown:
            dropdown.GetCurrentPattern(10005).QueryInterface(
                uia.IUIAutomationExpandCollapsePattern
            ).Expand()
            time.sleep(0.2)
            elements = root.FindAll(4, reader.automation.CreateTrueCondition())
            for index in range(elements.Length):
                element = elements.GetElement(index)
                if (element.CurrentControlType == 50007
                        and element.CurrentName in LANGUAGE_NAMES[language]):
                    element.GetCurrentPattern(10010).QueryInterface(
                        uia.IUIAutomationSelectionItemPattern
                    ).Select()
                    time.sleep(0.2)
                    button = by_id("ContinueButton")
                    if button and button.CurrentIsEnabled:
                        invoke(button)
                        return True
            return False
        settings = root.FindFirst(
            4, reader.automation.CreatePropertyCondition(30011, "SettingsButton")
        )
        if not settings:
            return False
        invoke(settings)
        time.sleep(0.2)
        for attempt in range(3):
            elements = root.FindAll(4, reader.automation.CreateTrueCondition())
            for index in range(elements.Length):
                element = elements.GetElement(index)
                name = element.CurrentName
                if name in LANGUAGE_NAMES[language]:
                    invoke(element)
                    return True
                if attempt == 0 and name in (
                    "Change language", "更改语言", "Alterar idioma", "Caption language", "字幕语言"
                ):
                    invoke(element)
            time.sleep(0.2)
        return False
    finally:
        reader.close()
