"""ONVIF PullPoint parsing: motion topics only, every transition kept."""

from unifi.onvif_events import envelope, motion_states, pin_host


def msg(topic, name, value):
    return (
        f"<tt:NotificationMessage><wsnt:Topic Dialect='x'>{topic}</wsnt:Topic>"
        f'<tt:Data><tt:SimpleItem Name="{name}" Value="{value}"/></tt:Data>'
        "</tt:NotificationMessage>"
    )


def test_motion_alarm_state():
    assert motion_states(msg("tns1:VideoSource/MotionAlarm", "State", "true")) == [True]
    assert motion_states(msg("tns1:VideoSource/MotionAlarm", "State", "false")) == [False]


def test_cell_motion_detector_keeps_start_and_stop():
    xml = msg("tns1:RuleEngine/CellMotionDetector/Motion", "IsMotion", "true") + msg(
        "tns1:RuleEngine/CellMotionDetector/Motion", "IsMotion", "false"
    )
    assert motion_states(xml) == [True, False]


def test_non_motion_topics_ignored():
    # LaView sends these as soon as it is dark; they must not open an event.
    xml = msg("tns1:VideoSource/ImageTooDark/ImagingService", "State", "true")
    assert motion_states(xml) == []
    assert motion_states("<Envelope/>") == []


def test_pin_host_ignores_camera_supplied_host():
    pin = lambda u: pin_host(u, "192.168.51.103:8000")
    assert pin("http://192.168.51.103:8000/event_service/0") == "http://192.168.51.103:8000/event_service/0"
    assert pin("https://evil.example:9/x?a=1") == "http://192.168.51.103:9/x?a=1"
    assert pin("http://user@10.0.0.9/onvif/events") == "http://192.168.51.103/onvif/events"


def test_envelope_escapes_user():
    assert "<Username>a&amp;b</Username>" in envelope("a&b", "pw", "<x/>")
