# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, unicode_literals
from sys import argv
from addon import run


def refresh_EPG():
    from kodiwrapper import KodiWrapper
    from yelo_bg_service import BackgroundService

    KodiWrapper.dialog_ok(KodiWrapper.get_localized_string(40001),
                          KodiWrapper.get_localized_string(40003))

    BackgroundService.cache_channel_epg()
    KodiWrapper.dialog_ok(KodiWrapper.get_localized_string(40001),
                          KodiWrapper.get_localized_string(40002))


if __name__ == '__main__':
    function = argv[1]

    if function == "refresh_epg":
        refresh_EPG()
    else:
        run(argv)
