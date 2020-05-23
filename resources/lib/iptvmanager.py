# -*- coding: utf-8 -*-
""" Kodi PVR Integration module """

from __future__ import absolute_import, division, unicode_literals

import logging
import socket
import json

_LOGGER = logging.getLogger('iptv-manager')

class IPTVManager:
    """ Code related to the Kodi PVR integration """

    def __init__(self, port):
        self.port = port


    def send(self, data):
        """Decorator to send over a socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', self.port))
        try:
            sock.send(json.dumps(data)) # pylint: disable=not-callable
        finally:
            sock.close()



    def send_channels(self, yelo_inst):
        self.send(dict(version=1, streams=yelo_inst.get_channels_iptv()))

    def send_epg(self, yelo_inst):
        tv_channels = yelo_inst.get_channels()
        self.send(dict(version=1, epg=yelo_inst.get_epg(tv_channels)))
