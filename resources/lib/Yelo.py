import inputstreamhelper
import xbmcgui
import xbmcplugin
import sys
from resources.lib.helpers.helpermethods import widevine_payload_package, get_from_cache
from resources.lib.helpers.helperclasses import UA
from resources.lib import YeloApi

PROTOCOL = 'mpd'
DRM = 'com.widevine.alpha'
LICENSE_URL = 'https://lwvdrm.yelo.prd.telenet-ops.be/WvLicenseProxy'

__handle__ = int(sys.argv[1])

if sys.version_info[0] == 3:
    from urllib.parse import quote
else:
    from urllib import quote

class Yelo(YeloApi.YeloApi):
    def __init__(self):
        super(Yelo, self).__init__()

    def play(self, channel):
        manifest_url = self.get_manifest(channel)
        device_id = get_from_cache("device_id")
        customer_id = get_from_cache("entitlements")["customer_id"]

        is_helper = inputstreamhelper.Helper(PROTOCOL, drm=DRM)
        if is_helper.check_inputstream():
            play_item = xbmcgui.ListItem(path=manifest_url)
            play_item.setMimeType('application/xml+dash')
            play_item.setContentLookup(False)
            play_item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
            play_item.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)
            play_item.setProperty('inputstream.adaptive.license_type', DRM)
            play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
            play_item.setProperty('inputstream.adaptive.license_key',
                                  LICENSE_URL + '|Content-Type=text%2Fplain%3Bcharset%3DUTF-8&User-Agent=' + quote(UA.UA()) +
                                  '|' + 'b{' +
                                  widevine_payload_package(device_id, customer_id) + '}' +
                                  '|JBlicense')
            play_item.setProperty('inputstream.adaptive.license_flags', "persistent_storage")
            xbmcplugin.setResolvedUrl(__handle__, True, listitem=play_item)

    def list_channels(self, is_folder=False):
        from resources.lib.kodiwrapper import KodiWrapper
        import dateutil.parser
        import datetime

        listing = []

        tv_channels = self.get_channels()
        epg = self.get_epg()

        for i in range(len(tv_channels)):
            name = (tv_channels[i]["channelIdentification"]["name"])
            squareLogo = tv_channels[i]["channelProperties"]["squareLogo"]
            stbUniqueName = tv_channels[i]["channelIdentification"]["stbUniqueName"]

            poster = ""
            guide = ""

            for index, item in enumerate(epg[name]):
                try:
                    now = datetime.datetime.utcnow().replace(second=0, microsecond=0)
                    start = dateutil.parser.parse(item["start"])
                    end = dateutil.parser.parse(item["stop"])

                    if start <= now <= end:
                        try:
                            prev_title = epg[name][index - 1]["title"] \
                                if "title" in epg[name][index - 1] else ""
                        except IndexError:
                            prev_title = ""

                        try:
                            next_title = epg[name][index + 1]["title"] \
                                if "title" in epg[name][index + 1] else ""
                        except IndexError:
                            next_title = ""

                        title = item["title"]  if "title" in item else ""

                        guide = self._create_guide_from_channel_info(prev_title, title, next_title)
                        poster = item["image"] if "image" in item else ""
                except:
                    continue

            list_item = KodiWrapper. \
                create_list_item(name, squareLogo, poster, {"plot": guide}, True, True)

            url = KodiWrapper.url_for("play", uniqueName=stbUniqueName)

            listing.append((url, list_item, is_folder))

        KodiWrapper.add_dir_items(listing)
        KodiWrapper.end_directory()
