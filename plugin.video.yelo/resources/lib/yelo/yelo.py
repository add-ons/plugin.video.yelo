import requests
import uuid
from datetime import datetime, timedelta
import os, sys
from xbmcplugin import SORT_METHOD_LABEL_IGNORE_THE
from resources.lib.helpers.dynamic_headers import *
from resources.lib.helpers.helpermethods import *
from resources.lib.statics.static import *
from resources.lib.helpers import helperclasses
import json
from tornado import gen, httpclient, ioloop, web
import xbmc

# region Python_check

if sys.version_info[0] == 3:
    from urllib.parse import quote_plus, unquote_plus
else:
    from urllib import quote_plus, unquote_plus
    from builtins import xrange as range

# endregion

FILE_NAME = "data.json"


class Errors():
    def __init__(self, testing, kodiwrapper):
        self.testing = not testing
        self.kodi_wrapper = kodiwrapper
        self.requests = requests

    def get_error_message(self, id):
        r = make_request(self.requests, "GET", "https://api.yeloplay.be/api/v1/masterdata?"
                                               "platform=Web&fields=errors",
                              default_headers, None, None, False, None, self.testing)

        errors = r.json()["masterData"]["errors"]
        res = [error for error in errors if error["id"] == id]

        if res:
            return res[0]["title"]["locales"]["en"], res[0]["subtitle"]["locales"]["en"]


class Prepare:
    def __init__(self, testing, kodiwrapper):
        self.testing = not testing
        self.kodi_wrapper = kodiwrapper
        self.get_l_string = kodiwrapper.get_localized_string
        self.session = requests.Session()

    def _prepare_request(self):
        r = make_request(self.session, "POST",
                              "https://api.yeloplay.be/api/v1/oauth/prepare",
                              json_header, None, json_prepare_message, False, None, self.testing)

        j = r.json()["OAuthPrepareParams"]

        self.append_json_to_file(FILE_NAME,
                                 {"OAuthPrepareParams": {
                                     'authorizeUrl': j["authorizeUrl"],
                                     'clientId': j["clientId"],
                                     'nonce': j["nonce"],
                                     'redirectUri': j["redirectUri"]
                                 }})

    def _authorize(self):
        OAuthPrepareParams = self.fetch_from_data("OAuthPrepareParams")

        authorize_Url = OAuthPrepareParams["authorizeUrl"]
        client_Id = OAuthPrepareParams["clientId"]
        nonce = OAuthPrepareParams["nonce"]
        state = self.create_State(20)
        redirect_Uri = quote_plus(OAuthPrepareParams["redirectUri"])

        r = make_request(self.session, "GET", "{}?client_id={}&state={}&nonce={}&redirect_uri={}"
                              .format(authorize_Url, client_Id, nonce, state, redirect_Uri)
                              + "&response_type=code&prompt=login", default_headers, None, None, False, None,
                              self.testing)

        return r.headers["Location"]

    def _register_device(self):
        r = make_request(self.session, "POST", "https://api.yeloplay.be/api/v1/device/register", json_header, None,
                              json_request_device, False, None, self.testing)
        j = r.json()

        if j["deviceRegistration"]["resultCode"] == "CREATED":
            self.append_json_to_file(FILE_NAME,
                                     {"IdTokens": {
                                         'deviceId': j["deviceRegistration"]["id"],
                                         'webId': j["deviceRegistration"]["deviceProperties"]["dict"][8]["value"]
                                     }})

    def login(self):
        self._prepare_request()
        self._register_device()
        self._authorize()

        self._login_do()

        callback_url = self._authorize()

        if self._callback(callback_url):
            self._verify_token()
            self._request_OAuthTokens()
            self._request_entitlement_and_postal()

            return True
        else:
            self.kodi_wrapper.dialog_ok(self.get_l_string(32006),
                                        self.get_l_string(32007))
            return False

    def _login_do(self):
        creds = helperclasses.Credentials(self.kodi_wrapper)
        if not creds.are_filled_in():
            self.kodi_wrapper.dialog_ok(self.get_l_string(32014),
                                        self.get_l_string(32015))
            self.kodi_wrapper.open_settings()
            creds.reload()

        make_request(self.session, "POST", "https://login.prd.telenet.be/openid/login.do",
                          form_headers, create_login_payload(creds.username, creds.password),
                          None, False, None, self.testing)

    def _callback(self, url):
        callbackKey = regex(r"(?<=code=)\w{0,32}", url)

        if not callbackKey:
            return False

        self.append_json_to_file(FILE_NAME, {"callbackKey": {"callbackKey": callbackKey}})

        make_request(self.session, "GET", url, default_headers, None, None, False, None, self.testing)

        return True

    def _verify_token(self):
        Ids = self.fetch_from_data("IdTokens")
        callbackKey = self.fetch_from_data("callbackKey")["callbackKey"]
        make_request(self.session, "POST", "https://api.yeloplay.be/api/v1/device/verify",
                          verify_device_header(Ids["deviceId"], callbackKey), None,
                          json_verify_data(Ids["deviceId"], Ids["webId"]),
                          False, None, self.testing)

    def append_json_to_file(self, file_name, json_data):
        path = self.kodi_wrapper.get_addon_data_path()

        if not os.path.exists(path):
            os.mkdir(path, 0o775)

        os.chdir(path)

        data = {}
        if os.path.isfile(file_name):
            with open(file_name, "r") as jsonFile:
                data = json.load(jsonFile)

        data.update(json_data)

        with open(file_name, "w") as jsonFile:
            json.dump(data, jsonFile)

    def fetch_from_data(self, key):
        with open(FILE_NAME, "r") as jsonFile:
            data = json.load(jsonFile)

        return data[key]

    def fetch_channel_list(self):
        postal = helperclasses.PostalCode(self.kodi_wrapper)

        # if postal is not filled in, in settings try to retrieve it from customerFeatures
        if not postal.are_filled_in():
            postal.postal_code = self.fetch_from_data("postal")["postal_code"]

            # if that does not seem to work..
            if postal.postal_code is None:
                self.kodi_wrapper.dialog_ok(self.get_l_string(32008),
                                            self.get_l_string(32009))
                self.kodi_wrapper.open_settings()
                postal.reload()

        r = make_request(self.session, "GET", "https://api.yeloplay.be/api/v1/epg/channel/list?platform=Web"
                                     "&postalCode={}&postalCode={}".format(postal.postal_code, postal.postal_code),
                              default_headers,
                              None, None, False, None, self.testing)
        return r.json()["serviceCatalog"]["tvChannels"]

    def _request_OAuthTokens(self):
        Ids = self.fetch_from_data("IdTokens")
        OAuthPrepareParams = self.fetch_from_data("OAuthPrepareParams")
        callbackKey = self.fetch_from_data("callbackKey")["callbackKey"]

        r = make_request(self.session, "POST", "https://api.yeloplay.be/api/v1/oauth/token",
                              token_header(Ids["deviceId"], callbackKey), False,
                              json_oauth_token_data(callbackKey,
                                                    unquote_plus(OAuthPrepareParams["redirectUri"])),
                              False, None, self.testing)

        j = r.json()["OAuthTokens"]

        if j["status"] == "SUCCESS":
            self.append_json_to_file(FILE_NAME, {"OAuthTokens": j})

    def create_State(self, size):
        return str(uuid.uuid4()).replace("-", "")[0:size]

    def _request_entitlement_and_postal(self):
        accessToken = self.fetch_from_data("OAuthTokens")["accessToken"]
        deviceId = self.fetch_from_data("IdTokens")["deviceId"]

        r = make_request(self.session, "GET", "https://api.yeloplay.be/api/v1/session/lookup?include=customerFeatures",
                              authorization_header(deviceId, accessToken),
                              None, None, False, None, self.testing)
        j = r.json()

        entitlements = [int(item["id"]) for item in j["linked"]["customerFeatures"]["entitlements"]]
        customer_Id = j["loginSession"]["user"]["links"]["customerFeatures"]
        postal_code = j["linked"]["customerFeatures"]["idtvLines"][0]["region"]

        self.append_json_to_file(FILE_NAME, {"entitlement": {"entitlementId": entitlements,
                                                             "customer_id": customer_Id}})
        self.append_json_to_file(FILE_NAME, {"postal": {"postal_code": postal_code}})


class YeloPlay(Prepare, Errors):
    def __init__(self, kodiwrapper, streaming_protocol, testing=False):
        Prepare.__init__(self, testing, kodiwrapper)
        Errors.__init__(self, testing, kodiwrapper)
        self.channel_schedules = {}
        self.streaming_protocol = streaming_protocol
        self.addon_url = kodiwrapper.get_addon_url()
    
    @gen.coroutine
    def fetch(session, url):
        request = httpclient.AsyncHTTPClient()
        resp = yield request.fetch(url)
        result = json.loads(resp.body.decode('utf-8'))
        raise gen.Return(result)

    @gen.coroutine
    def fetch_channels_schedules(self, channels):
        datetime = datetime.today().strftime("%Y%m%d%H")
        futures_list = []
        channels_schedules = []
        for channel in channels:
            url = "https://pubba.yelo.prd.telenet-ops.be/v1/events/schedule-time/outformat/json/lng/nl/start/{}/range/{}/channel/{}/".format(datetime, 1, channelId)
            futures_list.append(fetch(session, url))
        yield futures_list
        for x in futures_list:
            schedules = x.result().json()["schedule"]
            channelId = schedules[0].channelid
            self.channels_schedules[channelId] = [(broadcast_elem["title"], broadcast_elem["starttime"], broadcast_elem["endtime"],
                    broadcast_elem["poster"])
                    for schedule_elem in schedules for broadcast_elem in schedule_elem["broadcast"]]
        return

    def get_current_program_playing(self, schedule):
        timestamp = get_timestamp()

        if schedule:
            query = [(x[0], x[3]) for x in schedule if timestamp >= int(x[1]) and timestamp <= int(x[2])]

            if query:
                return query[0]

        return "", ""

    def list_channels(self, tv_channels, is_folder=True):
        import web_pdb; web_pdb.set_trace()
        listing = []
        entitlementId = self.fetch_from_data("entitlement")["entitlementId"]
        channels = []
        for j in range(len(tv_channels)):
            if (
                    not bool(tv_channels[j]["channelProperties"]["radio"])
                    and bool(tv_channels[j]["channelProperties"]["live"])
                    and any(tv_channels[j]["channelPolicies"]["linearEndpoints"])
                    and any(x in entitlementId for x in tv_channels[j]["channelAvailability"]["oasisId"])
            ):
                channels.append(tv_channels[j]["channelIdentification"]["channelId"])

        self.channels_schedules = yield self.fetch_channels_schedules(channels)

        for i in range(len(tv_channels)):
            if (
                    not bool(tv_channels[i]["channelProperties"]["radio"])
                    and bool(tv_channels[i]["channelProperties"]["live"])
                    and any(tv_channels[i]["channelPolicies"]["linearEndpoints"])
                    and any(x in entitlementId for x in tv_channels[i]["channelAvailability"]["oasisId"])
            ):

                name = tv_channels[i]["channelIdentification"]["name"]
                squareLogo = tv_channels[i]["channelProperties"]["squareLogo"]
                liveThumbnailURL = tv_channels[i]["channelProperties"]["liveThumbnailURL"]
                stbUniqueName = tv_channels[i]["channelIdentification"]["stbUniqueName"]
                channelId = tv_channels[i]["channelIdentification"]["channelId"]
                currently_playing, poster = self.get_current_program_playing(self.channel_schedules[channelId])
                xbmc.log("YELO TV - CHANNEL {} - {}".format(channelId, currently_playing))
                list_item = self.kodi_wrapper.\
                    create_list_item(name if sys.version_info[0] == 3 else name.encode('utf-8'),
                                     squareLogo, liveThumbnailURL, {"plot": currently_playing}, "true")
                url = self.kodi_wrapper.url_for("play_livestream", channel=stbUniqueName)
                self.kodi_wrapper.add_dir_item(url, list_item, 1)
        
        self.kodi_wrapper.end_directory()

    def play_live_stream(self, stream_url):
        bit_rate = helperclasses.BitRate(self.kodi_wrapper)
        deviceId = self.fetch_from_data("IdTokens")["deviceId"]
        customerId = self.fetch_from_data("entitlement")["customer_id"]

        self.kodi_wrapper.play_live_stream(deviceId, customerId, stream_url, bit_rate.bitrate)

    def select_manifest_url(self, channel):
        for i in range(0, 2):
            try:
                accessToken = self.fetch_from_data("OAuthTokens")["accessToken"]
                deviceId = self.fetch_from_data("IdTokens")["deviceId"]

                r = make_request(self.session, "POST", "https://api.yeloplay.be/api/v1/stream/start",
                                      authorization_header(deviceId, accessToken), None,
                                      stream_start_data(deviceId, channel, self.streaming_protocol),
                                      False, None, self.testing)

                j = r.json()
                if not j.get("errors"):
                    return j["stream"]["streamDescriptor"]["manifest"]
                else:
                    title, message = self.get_error_message(j["errors"][0]["code"])
                    self.kodi_wrapper.dialog_ok(title, message)

                    return False
            except ValueError:
                """ Session might be expired """
                self.login()
