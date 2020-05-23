# -*- coding: utf-8 -*-

import requests
import sys

from resources.lib.helpers.helperclasses import *
from resources.lib.helpers.helpermethods import *
from resources.lib.Exceptions import Exceptions
from resources.lib.YeloErrors import YeloErrors
from resources.lib.kodiwrapper import KodiWrapper

if sys.version_info[0] == 3:
    from urllib.parse import quote
else:
    from urllib import quote
    from builtins import xrange as range

BASE_URL = "https://api.yeloplay.be/api/v1"
CALLBACK_URL = "https://www.yeloplay.be/openid/callback"

session = requests.Session()
#session.verify = False
session.headers['User-Agent'] = UA.UA()


class YeloApi(object):
    def __init__(self):
        self.auth_tries = 0
        if not self.oauth_in_cache:
            self.execute_required_steps()

    @property
    def oauth_in_cache(self):
        return is_in_cache("OAuthTokens")

    def extract_auth_token(self, url):
        callback_key = regex(r"(?<=code=)\w{0,32}", url)
        return callback_key

    def execute_required_steps(self):
        self._authorize()
        self._login()
        self._register_device()
        self._request_oauth_tokens()
        self._get_entitlements()

    def _customer_features(self):
        device_id = get_from_cache("device_id")
        oauth_tokens = get_from_cache("OAuthTokens")

        resp = session.get(BASE_URL + "/session/lookup?include=customerFeatures",
                           headers={
                               "Content-Type": "application/json;charset=utf-8",
                               "X-Yelo-DeviceId": device_id,
                               "Authorization": authorization_payload(oauth_tokens["accessToken"])
                           })

        return resp.json()

    def _authorize(self):
        state = create_token(20)
        nonce = create_token(32)

        session.get("https://login.prd.telenet.be/openid/oauth/authorize"
                    "?client_id={}&state={}&nonce={}&redirect_uri={}"
                    "&response_type=code&prompt=login".
                    format("yelo", state, nonce, quote(CALLBACK_URL)),
                    allow_redirects=False)

    def _login(self):
        creds = Credentials()

        if not creds.are_filled_in():
            KodiWrapper.dialog_ok(KodiWrapper.get_localized_string(32014),
                                  KodiWrapper.get_localized_string(32015))
            KodiWrapper.open_settings()
            creds.reload()

        resp = session.post("https://login.prd.telenet.be/openid/login.do",
                            data=login_payload(creds.username, creds.password))

        last_response = resp.history[-1]

        try:
            if "Location" in last_response.headers:
                token = self.extract_auth_token(last_response.headers["Location"])
                if not token:
                    raise Exceptions.NotAuthorizedException()
                cache_to_file({"auth_token": token})
        except Exceptions.NotAuthorizedException:
            KodiWrapper.dialog_ok(KodiWrapper.get_localized_string(32006),
                                  KodiWrapper.get_localized_string(32007))

            if self.auth_tries < 2:
                self.auth_tries += 1

                KodiWrapper.open_settings()
                self._login()

    def _register_device(self):
        resp = session.post(BASE_URL + "/device/register",
                            headers={
                                "Content-Type": "application/json;charset=utf-8"
                            },
                            data=device_payload(),
                            allow_redirects=False)

        device_id = resp.json()["deviceRegistration"]["id"]
        cache_to_file({"device_id": device_id})

    def _request_oauth_tokens(self):
        auth_token = get_from_cache("auth_token")
        device_id = get_from_cache("device_id")

        resp = session.post(BASE_URL + "/oauth/token",
                            headers={
                                "Content-Type": "application/json;charset=utf-8",
                                "X-Yelo-DeviceId": device_id
                            },
                            data=oauth_payload(auth_token, CALLBACK_URL),
                            allow_redirects=False)

        j = resp.json()["OAuthTokens"]

        if j["status"] == "SUCCESS":
            cache_to_file({"OAuthTokens": j})

    def _refresh_oauth_token(self):
        device_id = get_from_cache("device_id")
        refresh_token = get_from_cache("OAuthTokens")["refreshToken"]

        resp = session.post(BASE_URL + "/oauth/token",
                            headers={
                                "Content-Type": "application/json;charset=utf-8",
                                "X-Yelo-DeviceId": device_id,
                            },
                            data=oauth_refresh_token_payload(refresh_token, CALLBACK_URL),
                            allow_redirects=False)

        j = resp.json()["OAuthTokens"]

        if j["status"] == "SUCCESS":
            cache_to_file({"OAuthTokens": j})

    def _start_stream(self, channel, max_tries=2):
        resp = None
        for _ in range(max_tries):
            device_id = get_from_cache("device_id")
            oauth_tokens = get_from_cache("OAuthTokens")

            try:
                resp = session.post(BASE_URL + "/stream/start",
                                    headers={
                                        "Content-Type": "application/json;charset=utf-8",
                                        "X-Yelo-DeviceId": device_id,
                                        "Authorization": authorization_payload(oauth_tokens["accessToken"])
                                    },
                                    data=stream_payload(device_id, channel))

                if resp.status_code == 401:
                    raise Exceptions.NotAuthorizedException("Unauthorized")
                break
            except Exceptions.NotAuthorizedException:
                self._refresh_oauth_token()

        if resp:
            j = resp.json()

            if not j.get("errors"):
                return resp.json()

            title, message = YeloErrors.get_error_message(session, j["errors"][0]["code"])
            KodiWrapper.dialog_ok(title, message)
            raise Exceptions.YeloException(message)

    def get_manifest(self, channel):
        res = self._start_stream(channel)
        return res["stream"]["streamDescriptor"]["manifest"]

    def _get_shedule(self, channel_id):
        from datetime import datetime

        today = datetime.today().strftime("%Y-%m-%d")
        r = session.get("https://pubba.yelo.prd.telenet-ops.be/v1/"
                        "events/schedule-day/outformat/json/lng/nl/channel/"
                        "{}/day/{}/".format(channel_id, today))

        return r.json()

    def _get_entitlements(self):
        if not is_in_cache("entitlements"):
            res = self._customer_features()
            entitlements = [int(item["id"]) for item in res["linked"]["customerFeatures"]["entitlements"]]
            customer_id = res["loginSession"]["user"]["links"]["customerFeatures"]

            cache_to_file({"entitlements": {
                "entitlementId": entitlements,
                "customer_id": customer_id}})

        return get_from_cache("entitlements")

    def _filter_channels(self, tv_channels):
        allowed_channels = []
        entitlement_ids = get_from_cache("entitlements")["entitlementId"]

        for i in range(len(tv_channels)):
            if (
                    not bool(tv_channels[i]["channelProperties"]["radio"])
                    and bool(tv_channels[i]["channelProperties"]["live"])
                    and any(tv_channels[i]["channelPolicies"]["linearEndpoints"])
                    and any(x in entitlement_ids for x in tv_channels[i]["channelAvailability"]["oasisId"])
            ):
                allowed_channels.append(tv_channels[i])

        return allowed_channels

    def get_channels(self):
        r = session.get(BASE_URL + "/epg/channel/list?platform=Web")
        tvChannelsFromApi = r.json()["serviceCatalog"]["tvChannels"]

        allowedTvChannelsFromApi = self._filter_channels(tvChannelsFromApi)
        return allowedTvChannelsFromApi

    def get_channels_iptv(self):
        allowedTvChannelsFromApi = self.get_channels()

        channels = []
        for channel in allowedTvChannelsFromApi:
            name = channel["channelIdentification"]["name"]
            id = channel["channelIdentification"]["name"]
            uniqueName = channel["channelIdentification"]["stbUniqueName"]
            logo = channel["channelProperties"]["squareLogo"]
            channels.append(dict(
                name=name,
                id=id,
                logo=logo,
                stream='plugin://plugin.video.yelo/play/id/{uniqueName}'.
                    format(uniqueName=uniqueName)))

        return channels

    def __epg(self, channel_id, dict_ref):
        channels = []

        data = self._get_shedule(channel_id)
        channel_name = data["schedule"][0]["name"]
        channel_id = data["schedule"][0]["channelid"]

        for broadcast in data["schedule"][0]["broadcast"]:
            try:
                channels.append(
                    {
                        "id": channel_id,
                        "start": timestamp_to_datetime(broadcast["starttime"]),
                        "stop": timestamp_to_datetime(broadcast["endtime"]),
                        "title": (broadcast["title"] or ""),
                        "description": (broadcast["shortdescription"] or ""),
                        "subtitle": (broadcast["contentlabel"] or ""),
                        "image": broadcast["image"]
                    })

                dict_ref.update({channel_name: channels})
            except:
                continue

    def _epg(self, tv_channels):
        from threading import Thread

        dict_ref = {}
        threads = []

        channel_ids = [item["id"] for item in tv_channels]

        for id in channel_ids:
            thread = Thread(target=self.__epg, args=(id, dict_ref))
            thread.start()
            threads.append(thread)

        # wait for all threads to terminate
        for thread in threads:
            thread.join()

        return dict_ref

    def get_epg(self, tv_channels):
        return self._epg(tv_channels)

    def _create_guide_from_channel_info(self, prev, now, next):
        guide = ""
        if prev:
            guide += "[B]Previously: [/B]" + "\n" + prev + "\n"
        if now:
            guide += "[B]Currently Playing: [/B]" + "\n" + now + "\n"
        if next:
            guide += "[B]Coming up next: [/B]" + "\n" + next + "\n"

        return guide
