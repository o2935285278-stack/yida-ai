import pytest

from yida_ai.config.i18n import TRANSLATIONS
from yida_ai.config.settings import AppSettings
from yida_ai.ui.onboarding import OnboardingFlow, OnboardingStep


@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "pt-BR"])
def test_first_language_choice_is_saved_without_changing_speech(locale):
    settings = AppSettings(speech_language="pt-BR", interface_language="zh-CN")
    flow = OnboardingFlow(settings)
    assert flow.step is OnboardingStep.INTERFACE
    flow.select_interface(locale)
    assert settings.interface_language == locale
    assert settings.speech_language == "pt-BR"


def test_four_language_settings_remain_independent_in_onboarding():
    settings = AppSettings()
    flow = OnboardingFlow(settings)
    flow.select_interface("pt-BR")
    flow.select_speech("zh-CN")
    flow.set_output_languages("en-US", "pt-BR")
    assert (
        settings.interface_language,
        settings.speech_language,
        settings.translation_language,
        settings.reply_language,
    ) == ("pt-BR", "zh-CN", "en-US", "pt-BR")


def test_three_interface_catalogs_have_identical_keys():
    expected = set(TRANSLATIONS["zh-CN"])
    assert set(TRANSLATIONS["en-US"]) == expected
    assert set(TRANSLATIONS["pt-BR"]) == expected
