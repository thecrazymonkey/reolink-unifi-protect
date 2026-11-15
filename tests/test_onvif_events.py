"""ONVIF PullPoint parsing: motion topics only, last state wins."""

from unifi.onvif_events import envelope, motion_state


def msg(topic, name, value):
    return (
        f"<tt:NotificationMessage><wsnt:Topic Dialect='x'>{topic}</wsnt:Topic>"
        f'<tt:Data><tt:SimpleItem Name="{name}" Value="{value}"/></tt:Data>'
        "</tt:NotificationMessage>"
    )


def test_motion_alarm_state():
    assert motion_state(msg("tns1:VideoSource/MotionAlarm", "State", "true")) is True
    assert motion_state(msg("tns1:VideoSource/MotionAlarm", "State", "false")) is False


def test_cell_motion_detector_and_last_wins():
    xml = msg("tns1:RuleEngine/CellMotionDetector/Motion", "IsMotion", "true") + msg(
        "tns1:RuleEngine/CellMotionDetector/Motion", "IsMotion", "false"
    )
    assert motion_state(xml) is False


def test_non_motion_topics_ignored():
    # LaView sends these as soon as it is dark; they must not open an event.
    xml = msg("tns1:VideoSource/ImageTooDark/ImagingService", "State", "true")
    assert motion_state(xml) is None
    assert motion_state("<Envelope/>") is None


def test_envelope_escapes_user():
    assert "<Username>a&amp;b</Username>" in envelope("a&b", "pw", "<x/>")
