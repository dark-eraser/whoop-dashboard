import os
from whoopy import WhoopClient

class WhoopClientSingleton:
    _instance = None

    def __new__(cls, config):
        if cls._instance is None:
            cls._instance = super(WhoopClientSingleton, cls).__new__(cls)
            cls._instance._init(config)
        return cls._instance

    def _init(self, config):
        self.client = None
        self.config = config
        self.token_file = ".tokens/whoop_token.json"
        self._setup_client()

    def _setup_client(self):
        if not os.path.exists(self.token_file):
            url, state = WhoopClient.auth_url(
                self.config["client_id"], self.config["client_secret"], self.config["redirect_uri"]
            )
            print("Please authorize the app by visiting this URL: ", url)
            code = input("Enter the authorization code: ")
            self.client = WhoopClient.authorize(
                code,
                self.config["client_id"],
                self.config["client_secret"],
                self.config["redirect_uri"],
            )
            self.client.store_token(self.token_file)
        else:
            self.client = WhoopClient.from_token(
                self.token_file, self.config["client_id"], self.config["client_secret"]
            )

    def get_client(self):
        return self.client
    