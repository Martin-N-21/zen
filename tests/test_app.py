from zen.tui.app import ZenApp


def test_app_title() -> None:
    assert ZenApp.TITLE == "zen"
