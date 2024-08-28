import asyncio
import threading
import ccxt.pro as ccxt
import ccxt as ccxt_base
from ..datamodel import OrderBook, Order, Trade, TradeList
import traceback
from copy import deepcopy
from queue import Queue


class OrderbookUpdater(threading.Thread):

    def __init__(self, pair: str, depth: int, exchange_name):
        super(OrderbookUpdater, self).__init__()
        self.__connection_condition = True
        self.pair = pair
        self.depth = depth
        exchange = getattr(ccxt, exchange_name)
        self.__exchange: ccxt.Exchange = exchange()
        self.__orderbook = None
        self.__orderbook_parsed: OrderBook = None
        self.__connection_condition = True

    def __del__(self):
        self.close()

    async def __subscribe_orderbook_async(self) -> None:
        while self.__connection_condition:
            try:
                self.__orderbook = await self.__exchange.watch_order_book(
                    self.pair, self.depth
                )
                self.__build_orderbook()
            except Exception as e:
                print(f"{self.__exchange.name} OrderbookUpdater Error: {e}")
        await self.__exchange.close()

    def run(self) -> None:
        asyncio.run(self.__subscribe_orderbook_async())

    def __build_orderbook(self):
        if self.__orderbook is None:
            return None
        if self.__orderbook_parsed is None:
            self.__orderbook_parsed = OrderBook(
                pair=self.pair,
                exchange=self.__exchange.name.lower(),
                asks=[
                    Order(price=ask[0], volume=ask[1])
                    for ask in self.__orderbook["asks"][:10]
                ],
                bids=[
                    Order(price=bid[0], volume=bid[1])
                    for bid in self.__orderbook["bids"][:10]
                ],
                timestamp=self.__orderbook["timestamp"],
            )
        else:
            self.__orderbook_parsed.timestamp = self.__orderbook["timestamp"]

            for i in range(len(self.__orderbook_parsed.asks)):
                self.__orderbook_parsed.asks[i].price = self.__orderbook["asks"][i][0]
                self.__orderbook_parsed.asks[i].volume = self.__orderbook["asks"][i][1]

            for i in range(len(self.__orderbook_parsed.bids)):
                self.__orderbook_parsed.bids[i].price = self.__orderbook["bids"][i][0]
                self.__orderbook_parsed.bids[i].volume = self.__orderbook["bids"][i][1]

    def get_orderbook(self):
        return self.__orderbook_parsed

    def close(self):
        self.__connection_condition = False


class TradeListUpdater(threading.Thread):

    def __init__(self, api_key: str, api_secret: str, pair: str, exchange_name: str):
        super(TradeListUpdater, self).__init__()
        self.pair = pair
        self.__api_key = api_key
        self.__secret = api_secret
        exchange = getattr(ccxt, exchange_name)
        self.__exchange: ccxt.Exchange = exchange(
            {
                "newUpdates": True,
                "apiKey": self.__api_key,
                "secret": self.__secret,
            }
        )
        self.__trades = []
        self.__parsed_trades: TradeList = TradeList([])
        self.__connection_condition = True

    def __del__(self):
        self.close()

    async def __subscribe_trades_async(self, pair: str):
        await self.__exchange.load_markets()
        while self.__connection_condition:
            try:
                trades = await self.__exchange.watch_my_trades(pair)
                for trade in trades:
                    self.__trades.append(trade)
                self.__parsed_trades = self.__build_trade_list()
            except Exception as e:
                traceback.print_exc()
                print(f"Error: {e}")
                print(trades)
        await self.__exchange.close()

    def run(self) -> None:
        asyncio.run(self.__subscribe_trades_async(self.pair))

    def __build_trade_list(self):
        if self.__trades is None:
            return None
        if self.__parsed_trades is None:
            self.__parsed_trades = TradeList(
                exchange=self.__exchange.name.lower(),
                pair=self.pair,
                trades=[
                    Trade(
                        timestamp=trade["timestamp"],
                        price=trade["price"],
                        volume=trade["amount"],
                        side=trade["side"],
                    )
                    for trade in self.__trades
                ],
            )
        else:
            for trade in self.__trades:
                self.__parsed_trades.trades.append(
                    Trade(
                        timestamp=trade["timestamp"],
                        price=trade["price"],
                        volume=trade["amount"],
                        side=trade["side"],
                    )
                )
        self.__trades.clear()
        return self.__parsed_trades

    def get_trade_list(self) -> TradeList:
        # copy parsed trades
        parsed_trades = deepcopy(self.__parsed_trades)
        self.__parsed_trades.trades.clear()
        return parsed_trades

    def close(self):
        self.__connection_condition = False
        # close the asyncio loop



class BalanceUpdater(threading.Thread):

    def __init__(self, api_key: str, api_secret: str, exchange_name: str):
        super(BalanceUpdater, self).__init__()
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.exchange_name = exchange_name
        exchange = getattr(ccxt, self.exchange_name)
        self.__exchange: ccxt.Exchange = exchange(
            {"apiKey": self.__api_key, "secret": self.__api_secret}
        )
        self.__balance = asyncio.run(self.__fetch_balance_async())
        self.__connection_condition = True

    def __del__(self):
        self.close()

    async def __subscribe_balance_async(self) -> None:
        await self.__exchange.load_markets()
        while self.__connection_condition:
            try:
                self.__balance = await self.__exchange.watch_balance()
            except Exception as e:
                print(f"Error: {e}")
        await self.__exchange.close()

    async def __fetch_balance_async(self):
        exchange = getattr(ccxt, self.exchange_name)
        new_exchange: ccxt.Exchange = exchange(
            {"apiKey": self.__api_key, "secret": self.__api_secret}
        )
        balance = await new_exchange.fetch_balance()
        await new_exchange.close()
        return balance

    def run(self) -> None:
        asyncio.run(self.__subscribe_balance_async())

    def get_balance(self):
        return self.__balance

    def close(self):
        self.__connection_condition = False


class OrdersUpdater(threading.Thread):

    def __init__(self, api_key: str, api_secret: str, exchange_name: str, symbol=None):
        super(OrdersUpdater, self).__init__()
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.exchange = getattr(ccxt, exchange_name)
        self.__exchange: ccxt.Exchange = self.exchange(
            {"apiKey": self.__api_key, "secret": self.__api_secret}
        )
        self.__symbol = symbol
        self.__orders = None
        self.__parsed_orders = []
        self.__order_dict = {}
        self.__connection_condition = True

    def __del__(self):
        self.close()

    async def __subscribe_orders_async(self) -> None:
        await self.__exchange.load_markets()
        self.__orders = await self.__exchange.fetch_open_orders(self.__symbol)
        self.__parse_orders()
        while self.__connection_condition:
            try:
                self.__orders = await self.__exchange.watch_orders()
                if self.__orders is None:
                    continue
                self.__parse_orders()
            except Exception as e:
                print(f"Error: {e}")
        await self.__exchange.close()

    def run(self) -> None:
        asyncio.run(self.__subscribe_orders_async())

    def get_orders(self):
        return self.__parsed_orders

    # async def __async_fetch_open_orders(self, symbol):
    #     new_exchange: ccxt.Exchange = self.exchange(
    #         {"apiKey": self.__api_key, "secret": self.__api_secret}
    #     )
    #     orders = await new_exchange.fetch_open_orders(symbol)
    #     await new_exchange.close()
    #     return orders

    # def __fetch_open_orders(self, symbol):
    #     return asyncio.run(self.__async_fetch_open_orders(symbol))

    def __parse_orders(self) -> None:
        for order in self.__orders:
            if (
                order["status"] == "canceled"
                or order["status"] == "closed"
                or order["status"] == "filled"
                or order["status"] == "rejected"
                or order["status"] == "cancelled"
                or order["status"] == "expired"
            ):
                self.__order_dict.pop(order["id"], None)
            if order["status"] == "open":
                self.__order_dict[order["id"]] = Order(
                    id=order["id"],
                    symbol=order["symbol"],
                    side=order["side"],
                    price=order["price"],
                    volume=order["amount"],
                )
        self.__parsed_orders = list(self.__order_dict.values())

    def close(self):
        self.__connection_condition = False


class OrderSubmitter(threading.Thread):
    def __init__(self, api_key: str, api_secret: str, exchange_name: str, queue: Queue):
        super(OrderSubmitter, self).__init__()
        self.__api_key: str = api_key
        self.__api_secret: str = api_secret
        self.exchange = getattr(ccxt, exchange_name)
        self.__exchange: ccxt.Exchange = self.exchange(
            {"apiKey": self.__api_key, "secret": self.__api_secret}
        )
        self.__queue: Queue = queue
        self.__result_queue: Queue = Queue()
        self.__order: Order = None

    def __del__(self):
        self.close()

    async def __submit_order_async(self):
        await self.__exchange.load_markets()
        while True:
            self.__order = self.__queue.get()
            if self.__order is None:
                break
            try:
                order = await self.__exchange.create_order(
                    symbol=self.__order.symbol,
                    type="limit",
                    side=self.__order.side,
                    amount=self.__order.volume,
                    price=self.__order.price,
                )
                self.__result_queue.put(order)
            except Exception as e:
                print(f"Error: {e}")
        await self.__exchange.close()
        self.__queue.task_done()

    def run(self) -> None:
        self.__order = asyncio.run(self.__submit_order_async())

    def create_order(self, order):
        self.__queue.put(order)
        return self.__result_queue.get()

    def close(self):
        self.__queue.put(None)


class BaseAsyncClient:

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        pair: str,
        depth: int,
        exchange_name: str,
        **kwargs,
    ):
        self.__orderbook_updater: OrderbookUpdater = kwargs.get(
            "orderbook_updater", None
        )
        self.__tradelist_updater: TradeListUpdater = kwargs.get(
            "tradelist_updater", None
        )
        self.__balance_updater: BalanceUpdater = kwargs.get("balance_updater", None)
        self.__orders_updater: OrdersUpdater = kwargs.get("orders_updater", None)
        self.__order_submitter: OrderSubmitter = kwargs.get("order_submitter", None)
        self.__order_submitter_queue: Queue = kwargs.get("order_submitter_queue", None)
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.exchange_name = exchange_name
        self.pair = pair
        self.depth = depth
        self.__initialize_updaters()
        self.__market: ccxt.Exchange = getattr(ccxt, self.exchange_name)(
            {"apiKey": self.__api_key, "api_secret": self.__api_secret}
        )

    def __del__(self):
        self.close()

    def __initialize_updaters(self):
        self.__orderbook_updater.start()
        self.__tradelist_updater.start()
        self.__balance_updater.start()
        if self.__orders_updater is not None:
            self.__orders_updater.start()
        self.__order_submitter.start()

    def get_orderbook(self) -> OrderBook:
        return self.__orderbook_updater.get_orderbook()

    def get_trade_list(self) -> TradeList:
        return self.__tradelist_updater.get_trade_list()

    def get_balance(self):
        return self.__balance_updater.get_balance()

    def close(self) -> None:
        self.__orderbook_updater.close()
        self.__tradelist_updater.close()
        self.__balance_updater.close()
        self.__orderbook_updater.join()
        self.__tradelist_updater.join()
        self.__balance_updater.join()
        if self.__orders_updater is not None:
            self.__orders_updater.close()
            self.__orders_updater.join()
        if self.__order_submitter is not None:
            self.__order_submitter.close()
            self.__order_submitter.join()

    def create_order(self, symbol: str, order: Order):
        if self.__market is None:
            raise ValueError("Market is not initialized")
        if order.type not in ["limit", "market"]:
            raise ValueError("Type must be either limit or market")
        if order.side not in ["buy", "sell"]:
            raise ValueError("Side must be either buy or sell")
        if order.type == "market" and order.price is not None:
            raise ValueError("Price must be None for market orders")
        return self.__order_submitter.create_order(order)

    def get_balance(self):
        return self.__balance_updater.get_balance()

    def get_orders(self, symbol=None):
        if self.__orders_updater is None:
            raise ValueError("Orders updater is not initialized")
        return self.__orders_updater.get_orders()


class BaseAsyncClientFactory:

    def __init__(self, exchange_name: str, **kwargs):

        self.exchange_name = exchange_name
        if self.exchange_name not in ccxt.exchanges:
            raise ValueError(f"Exchange {self.exchange_name} is not supported")
        self.__api_key = kwargs.get("api_key", None)
        self.__api_secret = kwargs.get("api_secret", None)

    def create_receiver(self, pair: str, depth: int, **kwargs) -> BaseAsyncClient:
        orderbook_updater = kwargs.get("orderbook_updater", None)
        if orderbook_updater is None:
            orderbook_updater = OrderbookUpdater(pair, depth, self.exchange_name)
        tradelist_updater = kwargs.get("tradelist_updater", None)

        if tradelist_updater is None:
            tradelist_updater = TradeListUpdater(
                api_key=self.__api_key,
                api_secret=self.__api_secret,
                pair=pair,
                exchange_name=self.exchange_name,
            )

        balance_updater = kwargs.get("balance_updater", None)
        if balance_updater is None:
            balance_updater = BalanceUpdater(
                api_key=self.__api_key,
                api_secret=self.__api_secret,
                exchange_name=self.exchange_name,
            )

        if self.__api_key != "" and self.__api_secret != "":
            orders_updater = kwargs.get("orders_updater", None)
            if orders_updater is None:
                orders_updater = OrdersUpdater(
                    api_key=self.__api_key,
                    api_secret=self.__api_secret,
                    exchange_name=self.exchange_name,
                    symbol=pair,
                )
        else:
            orders_updater = None

        if self.__api_key != "" and self.__api_secret != "":
            order_submitter_queue = Queue()
            order_submitter = OrderSubmitter(
                api_key=self.__api_key,
                api_secret=self.__api_secret,
                exchange_name=self.exchange_name,
                queue=order_submitter_queue,
            )

        return BaseAsyncClient(
            pair=pair,
            depth=depth,
            api_key=self.__api_key,
            api_secret=self.__api_secret,
            exchange_name=self.exchange_name,
            orderbook_updater=orderbook_updater,
            tradelist_updater=tradelist_updater,
            balance_updater=balance_updater,
            orders_updater=orders_updater,
            order_submitter=order_submitter,
            order_submitter_queue=order_submitter_queue,
        )
