# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmcaddon import Addon


class Credentials:
    def __init__(self):
        self.reload()

    def are_filled_in(self):
        return not (self.username is None or self.password is None
                    or self.username == '' or self.password == '')

    def reload(self):
        self.username = Addon().getSetting('username')
        self.password = Addon().getSetting('password')
