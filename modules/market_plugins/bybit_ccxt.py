from ..datamodel import OrderBook, TradeList, Order
from .base_api_client_pro import BaseAsyncClientFactory, BaseAsyncClient


class BybitAPI:
    def __init__(self, api_key="", api_secret=""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.__factory = BaseAsyncClientFactory(
            api_key=api_key, api_secret=api_secret, exchange_name="bybit"
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

    def get_balance(self, pair: str):
        client = self.client_list.get(pair)
        return client.get_balance() if client else None

    def get_orders(self, pair: str):
        client = self.client_list.get(pair)
        return client.get_orders() if client else None

    def create_order(self, symbol: str, order: Order):
        client = self.client_list.get(symbol)
        return client.create_order(symbol=symbol, order=order) if client else None