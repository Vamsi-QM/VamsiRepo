from app.phone_actions import parse_phone_action


def test_parse_open_whatsapp_action():
    action = parse_phone_action("hey bro open WhatsApp")

    assert action is not None
    assert action.reply == "Opening WhatsApp bro."
    assert action.action["type"] == "open_app"
    assert action.action["label"] == "WhatsApp"
    assert "com.whatsapp" in action.action["packages"]


def test_parse_open_phone_action_uses_dialer_intent():
    action = parse_phone_action("open my phone")

    assert action is not None
    assert action.action["type"] == "open_app"
    assert action.action["intent"] == "dialer"


def test_parse_unsupported_app_reports_supported_list():
    action = parse_phone_action("open random banking app")

    assert action is not None
    assert action.action == {"type": "unsupported_open_app", "requested": "random banking"}
    assert "I can open only these apps right now" in action.reply