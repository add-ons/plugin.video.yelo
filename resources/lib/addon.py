# -*- coding: utf-8 -*-

import logging
import routing

from resources.lib.Exceptions import Exceptions
from resources.lib.Yelo import Yelo

_LOGGER = logging.getLogger('plugin')
plugin = routing.Plugin()

# instantiate yelo object
yelo = Yelo()

@plugin.route('/')
def main_menu():
    yelo.list_channels()

@plugin.route('/play/id/<uniqueName>')
def play(uniqueName):
    try:
        yelo.play(uniqueName)
    except Exceptions.YeloException as e:
        _LOGGER.error(e)

@plugin.route('/iptv/channels')
def iptv_channels():
    from resources.lib.iptvmanager import IPTVManager
    port = int(plugin.args['port'][0])
    IPTVManager(port).send_channels(yelo)

@plugin.route('/iptv/epg')
def iptv_epg():
    from resources.lib.iptvmanager import IPTVManager
    port = int(plugin.args['port'][0])
    IPTVManager(port).send_epg(yelo)

def run():
    plugin.run()
