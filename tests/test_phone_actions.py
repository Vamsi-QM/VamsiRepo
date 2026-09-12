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

def test_parse_reply_tell_him_action():
    action = parse_phone_action("Reply tell him I am driving")

    assert action is not None
    assert action.reply == "Sending that reply through the latest WhatsApp notification bro."
    assert action.action == {
        "type": "reply_notification",
        "app": "whatsapp",
        "label": "WhatsApp",
        "text": "I am driving",
    }


def test_parse_reply_latest_whatsapp_action():
    action = parse_phone_action("Reply to latest WhatsApp: I will call later")

    assert action is not None
    assert action.reply == "Sending that reply through the latest WhatsApp notification bro."
    assert action.action == {
        "type": "reply_notification",
        "app": "whatsapp",
        "label": "WhatsApp",
        "text": "I will call later",
    }


def test_parse_reply_by_notification_number():
    action = parse_phone_action("Reply to 2: I am driving")

    assert action is not None
    assert action.reply == "Sending that reply through WhatsApp notification 2 bro."
    assert action.action == {
        "type": "reply_notification",
        "app": "whatsapp",
        "label": "WhatsApp",
        "text": "I am driving",
        "target_index": 2,
    }


def test_parse_reply_by_sender_name():
    action = parse_phone_action("Reply to Mom: I am driving")

    assert action is not None
    assert action.reply == "Sending that reply through WhatsApp notification from Mom bro."
    assert action.action == {
        "type": "reply_notification",
        "app": "whatsapp",
        "label": "WhatsApp",
        "text": "I am driving",
        "target_name": "Mom",
    }

def test_parse_reply_by_quoted_sender_name():
    action = parse_phone_action('Reply to "Some One Name": I am driving')

    assert action is not None
    assert action.action == {
        "type": "reply_notification",
        "app": "whatsapp",
        "label": "WhatsApp",
        "text": "I am driving",
        "target_name": "Some One Name",
    }


def test_parse_direct_whatsapp_by_number():
    action = parse_phone_action("Send WhatsApp to 9876543210: I am driving")

    assert action is not None
    assert action.reply == "Opening WhatsApp number 9876543210 with your message bro."
    assert action.action == {
        "type": "direct_whatsapp",
        "label": "WhatsApp",
        "text": "I am driving",
        "phone": "919876543210",
    }


def test_parse_direct_whatsapp_by_name():
    action = parse_phone_action("Send WhatsApp to Mom: I am driving")

    assert action is not None
    assert action.reply == "Opening WhatsApp contact Mom with your message bro."
    assert action.action == {
        "type": "direct_whatsapp",
        "label": "WhatsApp",
        "text": "I am driving",
        "target_name": "Mom",
    }


def test_parse_list_whatsapp_apps():
    action = parse_phone_action("Which WhatsApps are installed?")

    assert action is not None
    assert action.reply == "Checking installed WhatsApp apps bro."
    assert action.action == {"type": "list_whatsapp_apps"}


def test_parse_open_whatsapp_slot():
    action = parse_phone_action("Open WhatsApp 2")

    assert action is not None
    assert action.reply == "Opening WhatsApp 2 bro."
    assert action.action == {
        "type": "open_app",
        "app": "whatsapp 2",
        "label": "WhatsApp 2",
        "packages": [],
        "intent": "whatsapp_slot",
        "whatsapp_slot": 2,
    }


def test_parse_direct_whatsapp_by_slot_and_name():
    action = parse_phone_action("Send WhatsApp 2 to Mom: I am driving")

    assert action is not None
    assert action.reply == "Opening WhatsApp 2 contact Mom with your message bro."
    assert action.action == {
        "type": "direct_whatsapp",
        "label": "WhatsApp 2",
        "text": "I am driving",
        "whatsapp_slot": 2,
        "target_name": "Mom",
    }
