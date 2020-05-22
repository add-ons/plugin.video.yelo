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

class UA:
    @classmethod
    def UA(cls):
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' \
                                'AppleWebKit/537.36 (KHTML, like Gecko) ' \
                                'Chrome/81.0.4044.138 Safari/537.36'
