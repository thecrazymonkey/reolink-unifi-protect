"""ONVIF PullPoint motion events for generic RTSP cameras (LaView, Tapo, ...).

Subscribes to the camera's event service and reports motion on/off transitions.
Understands the two common motion topics: VideoSource/MotionAlarm (State) and
RuleEngine/CellMotionDetector/Motion (IsMotion).
"""

import asyncio
import base64
import datetime
import hashlib
import logging
import os
import re
import urllib.parse
from typing import Awaitable, Callable, Optional
from xml.sax.saxutils import escape

import aiohttp

_NOTIFY = re.compile(r"NotificationMessage>(.*?)</(?:\w+:)?NotificationMessage", re.S)
_TOPIC = re.compile(r"Topic[^>]*>([^<]+)<")
_ITEM = re.compile(r'SimpleItem Name="(State|IsMotion)" Value="(\w+)"')


def envelope(user: str, password: str, body: str) -> str:
    """SOAP 1.2 envelope with a WS-Security UsernameToken digest."""
    nonce = os.urandom(16)
    created = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    digest = base64.b64encode(
        hashlib.sha1(nonce + created.encode() + password.encode()).digest()
    ).decode()
    wsse = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss"
    return (
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Header>'
        f'<Security xmlns="{wsse}-wssecurity-secext-1.0.xsd"><UsernameToken>'
        f"<Username>{escape(user)}</Username>"
        f'<Password Type="{wsse}-username-token-profile-1.0#PasswordDigest">{digest}</Password>'
        f'<Nonce EncodingType="{wsse}-soap-message-security-1.0#Base64Binary">'
        f"{base64.b64encode(nonce).decode()}</Nonce>"
        f'<Created xmlns="{wsse}-wssecurity-utility-1.0.xsd">{created}</Created>'
        f"</UsernameToken></Security></s:Header><s:Body>{body}</s:Body></s:Envelope>"
    )


def pin_host(url: str, host: str) -> str:
    """Keep port and path from a camera-supplied URL but force the configured host,
    so credentials never go to an address the camera's reply names."""
    u = urllib.parse.urlsplit(url)
    ip = host.rsplit(":", 1)[0]
    netloc = f"{ip}:{u.port}" if u.port else ip
    return urllib.parse.urlunsplit(("http", netloc, u.path, u.query, ""))


def motion_state(xml: str) -> Optional[bool]:
    """Last motion state in a PullMessages response, None if it carries none."""
    state = None
    for msg in _NOTIFY.findall(xml):
        topic = _TOPIC.search(msg)
        item = _ITEM.search(msg)
        if topic and "Motion" in topic.group(1) and item:
            state = item.group(2).lower() == "true"
    return state


EV = "http://www.onvif.org/ver10/events/wsdl"
CAPS = '<GetCapabilities xmlns="http://www.onvif.org/ver10/device/wsdl"><Category>Events</Category></GetCapabilities>'
PULL = f'<PullMessages xmlns="{EV}"><Timeout>PT10S</Timeout><MessageLimit>32</MessageLimit></PullMessages>'
SUBSCRIBE = f'<CreatePullPointSubscription xmlns="{EV}"><InitialTerminationTime>PT120S</InitialTerminationTime></CreatePullPointSubscription>'
RENEW = '<Renew xmlns="http://docs.oasis-open.org/wsn/b-2"><TerminationTime>PT120S</TerminationTime></Renew>'


async def watch(
    host: str,
    user: str,
    password: str,
    on_motion: Callable[[bool], Awaitable[None]],
    logger: logging.Logger,
) -> None:
    """Never returns: (re)subscribes with backoff and reports motion transitions.

    ``host`` is ``ip:port`` of the ONVIF service. A lost subscription reports
    motion off first so an event can never stay open.
    """
    delay, active = 2.0, False
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {"Content-Type": "application/soap+xml"}
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def call(url: str, body: str) -> str:
            async with session.post(
                url, data=envelope(user, password, body), headers=headers
            ) as r:
                return await r.text()

        while True:
            try:
                caps = await call(f"http://{host}/onvif/device_service", CAPS)
                xaddr = re.search(r"Events>\s*<[^>]*XAddr>([^<]+)<", caps)
                if not xaddr:
                    raise RuntimeError(f"no event service: {caps[:200]}")
                sub = await call(pin_host(xaddr.group(1), host), SUBSCRIBE)
                found = re.search(r"Address>([^<]+)<", sub)
                if not found:
                    raise RuntimeError(f"subscribe failed: {sub[:200]}")
                pull_url = pin_host(found.group(1), host)
                logger.info("ONVIF events subscribed")
                delay = 2.0
                while True:
                    reply = await call(pull_url, PULL)
                    if "Fault" in reply:
                        raise RuntimeError(f"pull fault: {reply[:200]}")
                    state = motion_state(reply)
                    if state is not None and state != active:
                        active = state
                        await on_motion(state)
                    await call(pull_url, RENEW)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"ONVIF events lost ({e}); retry in {delay:.0f}s")
                if active:
                    active = False
                    await on_motion(False)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 120.0)
