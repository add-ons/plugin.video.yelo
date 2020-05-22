# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, unicode_literals
import sys
from xbmcaddon import Addon
import xbmc
import xbmcgui
import xbmcplugin


class KodiWrapper():  # pylint: disable=no-init
    @classmethod
    def get_addon_data_path(cls):
        if sys.version_info[0] == 3:
            profile = xbmc.translatePath(Addon().getAddonInfo('profile'))
        else:
            profile = xbmc.translatePath(Addon().getAddonInfo('profile')).decode("utf-8")
        return profile

    @classmethod
    def dialog_ok(cls, header, message):
        dialog = xbmcgui.Dialog()
        return dialog.ok(header, message)

    @classmethod
    def get_localized_string(cls, number):
        return Addon().getLocalizedString(number)

    @classmethod
    def create_list_item(cls, label, logo, fanart, extra_info=None, playable=False, refresh_item=False):

        playable = "true" if playable else "false"

        list_item = xbmcgui.ListItem()
        list_item.setLabel(label)
        list_item.setArt({'fanart': fanart, 'icon': logo, 'thumb': logo})

        if refresh_item:
            list_item.addContextMenuItems([("Refresh", 'Container.Refresh')])

        info = {'title': label}
        if extra_info:
            info.update(extra_info)

        list_item.setInfo('video', info)
        list_item.setProperty('IsPlayable', playable)

        return list_item

    @classmethod
    def url_for(cls, name, *args, **kwargs):
        import addon
        return addon.plugin.url_for(getattr(addon, name), *args, **kwargs)

    @classmethod
    def add_dir_items(cls, listing):
        from addon import plugin
        xbmcplugin.addDirectoryItems(plugin.handle, listing, len(listing))

    @classmethod
    def end_directory(cls):
        from addon import plugin
        xbmcplugin.endOfDirectory(plugin.handle)

    @classmethod
    def sort_method(cls, sort_method):
        from addon import plugin
        xbmcplugin.addSortMethod(plugin.handle, sort_method)

    @classmethod
    def open_settings(cls):
        Addon().openSettings()
