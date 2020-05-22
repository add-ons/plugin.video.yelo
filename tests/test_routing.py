# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Integration tests for Routing functionality"""

# pylint: disable=invalid-name,line-too-long

from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
import addon


xbmc = __import__('xbmc')
xbmcaddon = __import__('xbmcaddon')
xbmcgui = __import__('xbmcgui')
xbmcplugin = __import__('xbmcplugin')
xbmcvfs = __import__('xbmcvfs')

plugin = addon.plugin
ADDON = xbmcaddon.Addon()


class TestRouting(unittest.TestCase):
    """TestCase class"""

    @unittest.skipUnless(ADDON.settings.get('username'), 'Skipping as username is missing.')
    @unittest.skipUnless(ADDON.settings.get('password'), 'Skipping as password is missing.')
    def test_main_menu(self):
        """Main menu: /"""
        addon.run(['plugin://plugin.video.yelo/', '0', ''])
        self.assertEqual(plugin.url_for(addon.main_menu), 'plugin://plugin.video.yelo/')

    @unittest.skipUnless(ADDON.settings.get('username'), 'Skipping as username is missing.')
    @unittest.skipUnless(ADDON.settings.get('password'), 'Skipping as password is missing.')
    def test_play_eenhd(self):
        """Play: /play/id/eenhd"""
        addon.run(['plugin://plugin.video.yelo/play/id/eenhd', '0', ''])
        self.assertEqual(plugin.url_for(addon.play_id, channel_id='eenhd'), 'plugin://plugin.video.yelo/play/id/eenhd')
