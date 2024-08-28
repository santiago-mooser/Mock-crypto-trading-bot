# Data model for trading bot

from typing import List


class Trade:

    def __init__(self, timestamp: int, price: float, volume: float, side: str):
        self.timestamp = timestamp
        self.price = price
        self.volume = volume
        self.side = side

    def __str__(self):
        return f"Trade({self.timestamp}, {self.price}, {self.volume}, {self.side})"

    def __repr__(self):
        return f"Trade({self.timestamp}, {self.price}, {self.volume}, {self.side})"

    def __iter__(self):
        return iter([self.timestamp, self.price, self.volume, self.side])


class TradeList:

    def __init__(self, trades: List[Trade], exchange=None, pair=None):
        self.trades = trades
        self.exchange = exchange
        self.pair = pair

    def __str__(self):
        return f"TradeList({self.trades})"

    def __repr__(self):
        return f"TradeList({self.trades})"

    def __iter__(self):
        return iter(self.trades)

    def __len__(self):
        return len(self.trades)


class Order:

    def __init__(self, price: float, volume: float, exchange="", side="", id="", symbol="") -> None:
        self.id = id
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.exchange = exchange
        self.side = side
        self.type = "limit"

    def __str__(self) -> str:
        return f"Order(exchange={self.exchange},id={self.id},symbol='{self.symbol}',price={self.price},volume={self.volume},side='{self.side})'"

    def __repr__(self) -> str:
        return f"Order(exchange={self.exchange},id={self.id},symbol='{self.symbol}',price={self.price},volume={self.volume},side='{self.side})'"

    def __iter__(self):
        return iter([self.price, self.volume])
    def __eq__(self, other_order):
        """Overrides the default implementation"""
        if isinstance(other_order, Order):
            return (self.price == other_order.price) and (self.side == other_order.side) and (self.volume == other_order.volume) and (self.exchange == other_order.exchange) and (self.symbol == other_order.symbol)
        return False

class OrderBook:

    def __init__(self, timestamp: int, asks: List[Order], bids: List[Order], exchange=None, pair=None):
        self.timestamp = timestamp
        self.asks = asks
        self.bids = bids
        self.exchange = exchange
        self.pair = None

    def __str__(self):
        return f"OrderBook(\nexchange={self.exchange},\npair={self.pair},\ntimestamp={self.timestamp},\nbids={self.bids},\nasks={self.asks})"

    def __repr__(self):
        return f"OrderBook(\nexchange={self.exchange},\npair={self.pair},\ntimestamp={self.timestamp},\nbids={self.bids},\nasks={self.asks})"

    def __iter__(self):
        return iter([self.timestamp, self.asks, self.bids])

    def __len__(self):
        return len(self.asks) + len(self.bids)
