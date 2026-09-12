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


def test_parse_open_command_with_question_mark():
    action = parse_phone_action("Open YouTube?")

    assert action is not None
    assert action.reply == "Opening YouTube bro."


def test_parse_unsupported_app_reports_supported_list():
    action = parse_phone_action("open random banking app")

    assert action is not None
    assert action.action == {"type": "unsupported_open_app", "requested": "random banking"}
    assert "I can open only these apps right now" in action.reply


def test_parse_whatsapp_notification_action():
    action = parse_phone_action("Read latest WhatsApp message")

    assert action is not None
    assert action.reply == "Checking your WhatsApp notifications bro."
    assert action.action == {
        "type": "read_notifications",
        "app": "whatsapp",
        "label": "WhatsApp notifications",
        "limit": 5,
    }


def test_parse_general_notification_action_with_question_mark():
    action = parse_phone_action("Any notifications bro?")

    assert action is not None
    assert action.reply == "Checking your notifications bro."
    assert action.action == {
        "type": "read_notifications",
        "app": "",
        "label": "notifications",
        "limit": 5,
    }