# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, unicode_literals


class YeloErrors():  # pylint: disable=no-init
    @classmethod
    def get_error_message(cls, session, errid):
        resp = session.get("https://api.yeloplay.be/api/v1/masterdata?platform=Web&fields=errors")

        errors = resp.json()["masterData"]["errors"]

        res = next((error for error in errors if error["id"] == errid), "")

        if not res:
            return None

        return res["title"]["locales"]["en"], res["subtitle"]["locales"]["en"]
