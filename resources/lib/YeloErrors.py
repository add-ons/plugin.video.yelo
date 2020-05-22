class YeloErrors():
    @classmethod
    def get_error_message(cls, session, id):
        r = session.get("https://api.yeloplay.be/api/v1/masterdata?"
                                         "platform=Web&fields=errors")

        errors = r.json()["masterData"]["errors"]

        res = next((error for error in errors if error["id"] == id), "")

        if res:
            return res["title"]["locales"]["en"], res["subtitle"]["locales"]["en"]