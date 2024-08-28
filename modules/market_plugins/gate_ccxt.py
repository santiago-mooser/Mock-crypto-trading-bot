from ..datamodel import OrderBook, TradeList
from .base_api_client_pro import BaseAsyncClient, BaseAsyncClientFactory


class GateAPI:
    def __init__(self, api_key="", api_secret=""):
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.__factory = BaseAsyncClientFactory(
            api_key=self.__api_key, api_secret=self.__api_secret, exchange_name="gate"
        )
        self.client_list: dict[str, BaseAsyncClient] = {}

    def __del__(self):
        for client in self.client_list.values():
            client.close()

    def subscribe_pair(self, pair: str, depth: int):
        self.client_list.update({pair: self.__factory.create_receiver(pair, depth)})

    def get_order_book(self, pair: str) -> OrderBook | None:
        return self.client_list[pair].get_orderbook()

    def get_trade_list(self, pair: str) -> TradeList | None:
        return self.client_list[pair].get_trade_list()

    def close(self):
        for client in self.client_list.values():
            client.close()
        self.client_list.clear()

    def get_position(self, pair: str):
        client = self.client_list.get(pair)
        return client.get_balance() if client else None

    def get_orders(self, pair: str):
        client = self.client_list.get(pair)
        return client.get_orders(pair) if client else None

    def fetch_orders(self, pair: str):
        client = self.client_list.get(pair)
        return client.get_orders(pair) if client else None

    def get_balance(self, pair: str):
        client = self.client_list.get(pair)
        return client.get_balance() if client else None

    def create_order(self, symbol: str, type: str, side: str, amount: float, price: float):
        client = self.client_list.get(symbol)
        return client.create_order(symbol, type, side, amount, price) if client else None