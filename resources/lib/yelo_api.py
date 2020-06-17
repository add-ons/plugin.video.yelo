# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, unicode_literals
import threading
import time
import requests

from data import USER_AGENT
from helpers.helperclasses import Credentials
from helpers.helpermethods import (authorization_payload, cache_to_file, create_token, device_payload, get_from_cache,
                                   is_in_cache, device_authorize,
                                   login_payload, oauth_payload, oauth_refresh_token_payload, regex, stream_payload,
                                   timestamp_to_datetime)
from kodiwrapper import KodiWrapper
from yelo_errors import YeloErrors
from yelo_exceptions import NotAuthorizedException, YeloException


try:  # Python 3
    from urllib.parse import quote
except ImportError:  # Python 2
    from urllib2 import quote

BASE_URL = "https://api.yeloplay.be/api/v1"
CALLBACK_URL = "https://www.yeloplay.be/openid/callback"

MAXTHREADS = 5
SEMAPHORE = threading.Semaphore(value=MAXTHREADS)


class YeloApi(object):  # pylint: disable=useless-object-inheritance
    session = requests.Session()
    session.verify = False
    session.headers['User-Agent'] = USER_AGENT

    def __init__(self):
        self.auth_tries = 0
        if not self.oauth_in_cache:
            self.execute_required_steps()

    @property
    def oauth_in_cache(self):
        return is_in_cache("OAuthTokens")

    @staticmethod
    def extract_auth_token(url):
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

        if not oauth_tokens:
            return {}

        resp = self.session.get(BASE_URL + "/session/lookup?include=customerFeatures",
                                headers={
                                    "Content-Type": "application/json;charset=utf-8",
                                    "X-Yelo-DeviceId": device_id,
                                    "Authorization": authorization_payload(oauth_tokens.get('accessToken'))
                                })
        return resp.json()

    def _authorize(self):
        state = create_token(20)
        nonce = create_token(32)

        self.session.get("https://login.prd.telenet.be/openid/oauth/authorize"
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

        resp = self.session.post("https://login.prd.telenet.be/openid/login.do",
                                 data=login_payload(creds.username, creds.password))

        last_response = resp.history[-1]

        try:
            if "Location" in last_response.headers:
                token = self.extract_auth_token(last_response.headers.get('Location'))
                if not token:
                    raise NotAuthorizedException()
                cache_to_file({"auth_token": token})
        except NotAuthorizedException:
            KodiWrapper.dialog_ok(KodiWrapper.get_localized_string(32006),
                                  KodiWrapper.get_localized_string(32007))

            if self.auth_tries < 2:
                self.auth_tries += 1

                KodiWrapper.open_settings()
                self._login()

    def _register_device(self):
        resp = self.session.post(BASE_URL + "/device/register",
                                 headers={
                                     "Content-Type": "application/json;charset=utf-8"
                                 },
                                 data=device_payload(),
                                 allow_redirects=False)

        device_id = resp.json().get('deviceRegistration').get('id')
        cache_to_file({"device_id": device_id})

    def _request_oauth_tokens(self):
        auth_token = get_from_cache("auth_token")
        device_id = get_from_cache("device_id")

        resp = self.session.post(BASE_URL + "/oauth/token",
                                 headers={
                                     "Content-Type": "application/json;charset=utf-8",
                                     "X-Yelo-DeviceId": device_id
                                 },
                                 data=oauth_payload(auth_token, CALLBACK_URL),
                                 allow_redirects=False)

        j = resp.json().get('OAuthTokens')

        if j and j.get('status') == 'SUCCESS':
            cache_to_file({"OAuthTokens": j})

    def _refresh_oauth_token(self):
        device_id = get_from_cache("device_id")
        refresh_token = get_from_cache("OAuthTokens").get('refreshToken')

        resp = self.session.post(BASE_URL + "/oauth/token",
                                 headers={
                                     "Content-Type": "application/json;charset=utf-8",
                                     "X-Yelo-DeviceId": device_id,
                                 },
                                 data=oauth_refresh_token_payload(refresh_token, CALLBACK_URL),
                                 allow_redirects=False)

        j = resp.json().get('OAuthTokens')

        if j and j.get('status') == "SUCCESS":
            cache_to_file({"OAuthTokens": j})

    def _start_stream(self, channel, max_tries=2):
        resp = None
        for _ in range(max_tries):
            device_id = get_from_cache("device_id")
            oauth_tokens = get_from_cache("OAuthTokens")

            try:
                resp = self.session.post(BASE_URL + "/stream/start",
                                         headers={
                                             "Content-Type": "application/json;charset=utf-8",
                                             "X-Yelo-DeviceId": device_id,
                                             "Authorization": authorization_payload(oauth_tokens["accessToken"])
                                         },
                                         data=stream_payload(device_id, channel))

                if resp.status_code == 401:
                    raise NotAuthorizedException("Unauthorized")
                if resp.status_code == 403:
                    response_data = resp.json()
                    devices_registered = response_data["stream"]["authorizationResult"]["authorizedDevices"]
                    devices_maximum = response_data["stream"]["authorizationResult"]["allowedDevices"]
                    if devices_maximum - devices_registered == 0:
                        title = "Telenet fout"
                        message = "Geen toestellen meer beschikbaar"
                        KodiWrapper.dialog_ok(title, message)
                    else:
                        resp = self.session.post(BASE_URL + "/device/authorize",
                                                 headers={
                                                     "Content-Type": "application/json;charset=utf-8",
                                                     "X-Yelo-DeviceId": device_id,
                                                     "Authorization": authorization_payload(oauth_tokens["accessToken"])
                                                 },
                                                 data=device_authorize(device_id, "YeloPlay"))
                        resp = self.session.post(BASE_URL + "/stream/start",
                                                 headers={
                                                     "Content-Type": "application/json;charset=utf-8",
                                                     "X-Yelo-DeviceId": device_id,
                                                     "Authorization": authorization_payload(oauth_tokens["accessToken"])
                                                 },
                                                 data=stream_payload(device_id, channel))

                break
            except NotAuthorizedException:
                self._refresh_oauth_token()

        if not resp:
            raise YeloException('Could not authenticate to play channel %s' % channel)

        response_data = resp.json()

        if response_data.get("errors"):
            title, message = YeloErrors.get_error_message(self.session, response_data["errors"][0]["code"])
            KodiWrapper.dialog_ok(title, message)
            raise YeloException(message)

        return response_data

    def get_manifest(self, channel):
        res = self._start_stream(channel)
        stream = res.get('stream')
        if not stream:
            raise YeloException('No stream for channel %s' % channel)
        streamdesc = stream.get('streamDescriptor')
        if not streamdesc:
            raise YeloException('No stream descriptor for channel %s' % channel)
        manifest = streamdesc.get('manifest')
        if not manifest:
            raise YeloException('No manifest for channel %s' % channel)
        return manifest

    def _get_entitlements(self):
        if not is_in_cache("entitlements"):
            res = self._customer_features()
            entitlements = [int(item["id"]) for item in res["linked"]["customerFeatures"]["entitlements"]]
            customer_id = res["loginSession"]["user"]["links"]["customerFeatures"]

            cache_to_file({"entitlements": {
                "entitlementId": entitlements,
                "customer_id": customer_id}})

        return get_from_cache("entitlements")

    @staticmethod
    def _filter_channels(tv_channels):
        allowed_channels = []
        entitlements = get_from_cache('entitlements')
        if not entitlements:
            return []

        entitlement_ids = entitlements.get('entitlementId')
        if not entitlement_ids:
            return []

        for tv_channel in tv_channels:
            if (
                    bool(tv_channel["channelProperties"]["live"])
                    and any(tv_channel["channelPolicies"]["linearEndpoints"])
                    and any(x in entitlement_ids for x in tv_channel["channelAvailability"]["oasisId"])
            ):
                allowed_channels.append(tv_channel)

        return allowed_channels

    def get_channels(self):
        resp = self.session.get(BASE_URL + "/epg/channel/list?platform=Web")
        tv_channels = resp.json()["serviceCatalog"]["tvChannels"]
        allowed_tv_channels = self._filter_channels(tv_channels)
        return allowed_tv_channels

    def get_channels_iptv(self):
        allowed_tv_channels = self.get_channels()

        channels = []
        for channel in allowed_tv_channels:
            name = channel.get('channelIdentification', {}).get('name')
            epg_id = channel.get('channelIdentification', {}).get('name')
            channel_id = channel.get('channelIdentification', {}).get('stbUniqueName')
            logo = channel.get('channelProperties', {}).get('squareLogo')
            channels.append(dict(
                name=name,
                id=epg_id,
                logo=logo,
                stream=KodiWrapper.url_for('play_id', channel_id=channel_id),
            ))
        return channels

    def _get_schedule(self, channel_id):
        from datetime import datetime

        today = datetime.today().strftime("%Y-%m-%d")
        resp = self.session.get("https://pubba.yelo.prd.telenet-ops.be/v1/"
                                "events/schedule-day/outformat/json/lng/nl/channel/"
                                "{}/day/{}/".format(channel_id, today))
        return resp.json()["schedule"]

    def _get_schedule_time(self, channel_id):
        from datetime import datetime

        today = datetime.today().strftime("%Y%m%d%H")
        resp = self.session.get("https://pubba.yelo.prd.telenet-ops.be/v1/"
                                "events/schedule-time/outformat/json/lng/nl/start/"
                                "{}/range/{}/channel/{}/".format(today, 2, channel_id))
        return resp.json()["schedule"]

    def __epg(self, channel_id, dict_ref, full):
        SEMAPHORE.acquire()

        channels = []

        if full:
            data = self._get_schedule(channel_id)
        else:
            data = self._get_schedule_time(channel_id)

        channel_name = data[0]["name"]
        channel_id = data[0]["channelid"]

        for broadcast in data[0]["broadcast"]:
            channels.append(dict(
                id=channel_id,
                start=timestamp_to_datetime(broadcast.get('starttime')),
                stop=timestamp_to_datetime(broadcast.get('endtime')),
                title=broadcast.get('title', ''),
                description=broadcast.get('shortdescription'),
                subtitle=broadcast.get('contentlabel'),
                image=broadcast.get('image'),
            ))
            dict_ref.update({channel_name: channels})

        time.sleep(0.01)
        SEMAPHORE.release()

    def _epg(self, tv_channels, full):
        dict_ref = {}
        threads = []

        channel_ids = [item["id"] for item in tv_channels]

        for channel_id in channel_ids:
            thread = threading.Thread(target=self.__epg, args=(channel_id, dict_ref, full))
            thread.start()
            threads.append(thread)

        # wait for all threads to terminate
        for thread in threads:
            thread.join()

        return dict_ref

    def get_epg(self, tv_channels, full=True):
        return self._epg(tv_channels, full)

    @staticmethod
    def _create_guide_from_channel_info(previous, current, upcoming):
        guide = ""
        if previous:
            guide += "[B]Previously: [/B]\n%s\n" % previous
        if current:
            guide += "[B]Currently playing: [/B]\n%s\n" % current
        if upcoming:
            guide += "[B]Coming up next: [/B]\n%s\n" % upcoming

        return guide
