import asyncio
import hashlib
import hmac
import threading
import time
import traceback
from queue import Queue
from typing import List, Optional

import requests
import ujson as json
from websockets.asyncio.client import connect

from ..datamodel import Order, OrderBook, Trade, TradeList
from .plugin_api import APIClient


class OrderbookUpdater(threading.Thread):
    """
    A thread-based class for updating and maintaining an orderbook for a specific trading pair.

    This class connects to a WebSocket endpoint, subscribes to orderbook updates,
    and continuously updates an internal representation of the orderbook.

    Attributes:
        pair (str): The trading pair to track (e.g., 'BTC/USD').
        depth (int): The depth of the orderbook to maintain.
        exchange_name (str): The name of the exchange being used.

    The class uses a WebSocket connection to receive real-time updates and
    maintains both a raw and a parsed version of the orderbook. The parsed
    version is accessible through the get_orderbook() method.
    """

    def __init__(
        self,
        pair: str,
        exchange_name: str,
        endpoint_url: str,
        subscription_payload: dict,
    ):
        super(OrderbookUpdater, self).__init__()
        self.pair = pair
        self.exchange_name = exchange_name
        self.__orderbook = None
        self.__orderbook_parsed: OrderBook = None
        self.__socket = None
        self.__endpoint = endpoint_url
        self.__subscription_payload = subscription_payload
        self.__connection_condition = True

    def __del__(self):
        self.close()

    def stop(self):
        self.__connection_condition = False

    def run(self):
        asyncio.run(self.__run())

    async def __run(self):
        async with connect(self.__endpoint) as websocket:
            self.__socket = websocket
            await websocket.send(json.dumps(self.__subscription_payload))

            while self.__connection_condition:
                try:
                    self.__orderbook = json.loads(await websocket.recv())
                    self.__build_orderbook()
                except Exception as e:
                    print(f"Error in websocket connection: {e}")
                    traceback.print_exc()
                    print(self.__orderbook)
                    break
            print("OrderbookUpdater: Closing websocket")
            await websocket.close()
            print("OrderbookUpdater: Socket closed")

    def __build_orderbook(self):
        if self.__orderbook is None:
            return None

        orderbook = self.__orderbook.get("payload", {})

        asks = orderbook.get("asks", [])
        bids = orderbook.get("bids", [])

        if self.__orderbook_parsed is None:

            ask_orders = []
            for i in range(10):
                if i < len(asks):
                    ask_orders.append(
                        Order(price=float(asks[i]["r"]), volume=float(asks[i]["a"]))
                    )
                else:
                    ask_orders.append(Order(price=0.0, volume=0.0))

            bid_orders = []
            for i in range(10):
                if i < len(bids):
                    bid_orders.append(
                        Order(price=float(bids[i]["r"]), volume=float(bids[i]["a"]))
                    )
                else:
                    bid_orders.append(Order(price=0.0, volume=0.0))

            self.__orderbook_parsed = OrderBook(
                pair=self.pair,
                exchange=self.exchange_name.lower(),
                asks=ask_orders,
                bids=bid_orders,
                timestamp=self.__orderbook.get("sent"),
            )
        else:
            self.__orderbook_parsed.timestamp = self.__orderbook.get("sent")

            for i in range(min(10, len(asks))):
                self.__orderbook_parsed.asks[i].price = float(asks[i]["r"])
                self.__orderbook_parsed.asks[i].volume = float(asks[i]["a"])

            for i in range(min(10, len(bids))):
                self.__orderbook_parsed.bids[i].price = float(bids[i]["r"])
                self.__orderbook_parsed.bids[i].volume = float(bids[i]["a"])

    def get_orderbook(self):
        return self.__orderbook_parsed

    async def __close(self):
        if self.__socket:
            await self.__socket.close()

    def close(self):
        self.__connection_condition = False

    def stop(self):
        self.__connection_condition = False


class TradeListUpdater(threading.Thread):
    """
    A thread-based class for updating and maintaining a list of recent trades for a specific trading pair.

    This class connects to a WebSocket endpoint, subscribes to trade updates,
    and continuously updates an internal representation of the recent trades.

    Attributes:
        pair (str): The trading pair to track (e.g., 'BTC/USD').
        max_trades (int): The maximum number of trades to keep in memory.
        exchange_name (str): The name of the exchange being used.
    """

    def __init__(
        self,
        pair: str,
        exchange_name: str,
        endpoint_url: str,
        subscription_payload: dict,
        order_id_queue: Queue,
    ):
        super(TradeListUpdater, self).__init__()
        self.pair = pair
        self.exchange_name = exchange_name
        self.__trades: List[Trade] = []
        self.__socket = None
        self.__endpoint = endpoint_url
        self.__subscription_payload = subscription_payload
        self.__connection_condition = True
        self.__lock = threading.Lock()
        self.__order_id_queue = order_id_queue

    def __del__(self):
        self.stop()

    def stop(self):
        self.__connection_condition = False

    def run(self):
        asyncio.run(self.__run())

    async def __run(self):
        async with connect(self.__endpoint) as websocket:
            self.__socket = websocket
            await websocket.send(json.dumps(self.__subscription_payload))

            while self.__connection_condition:
                try:
                    trade_data = json.loads(await websocket.recv())
                    self.__process_trade(trade_data)
                except Exception as e:
                    print(f"Error in websocket connection: {e}")
                    break
            print("TradesUpdater: closing websocket")
            await websocket.close()
            print("TradesUpdater: websocket closed")

    def __process_trade(self, trade_data):
        trades = trade_data.get("payload", {})
        for trade in trades:
            self.__order_id_queue.put(
                Trade(
                    id=trade.get("i"),
                    timestamp=trade.get("x"),
                    price=trade.get("r"),
                    volume=trade.get("a"),
                    side=["buy" if trade.get("t") == 1 else "sell"],
                )
            )


class OrderSubmitter(threading.Thread):
    def __init__(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        pair: str,
        order_id_queue: Queue,
        **kwargs,
    ):
        super().__init__()
        self.exchange = exchange
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.pair = pair
        self.__queue = Queue()
        self.__order_id_queue = order_id_queue
        self.__connection_condition = True

    def __del__(self):
        self.stop()

    def stop(self):
        self.__connection_condition = False
        self.__queue.put_nowait(None)

    def run(self):
        asyncio.run(self.__run())

    def submit_trade(self, order: Order):
        self.__queue.put_nowait(order)

    async def __run(self):
        while self.__connection_condition:
            try:
                order = self.__queue.get()
                if order is None:  # None is used as a signal to stop
                    break

                self.__order_id_queue.put(
                    {
                        "order_id": self.__submit_order(order)
                        .get("payload", {})
                        .get("oid", "")
                    }
                )
                self.__queue.task_done()

            except Exception as e:
                print(f"Error submitting trade: {e}")
                traceback.print_exc()
        print("Closed Order Submitter")

    def __submit_order(self, order: Order):
        try:
            # Bitso API endpoint for creating an order
            url = "https://api.bitso.com/v3/orders/"

            # Prepare the payload
            payload = {
                "book": self.pair,
                "side": order.side,
                "type": order.type,
                "major": order.volume,
                "price": order.price,
            }

            # Prepare the authentication
            nonce = str(int(time.time() * 1000))
            message = nonce + "POST" + "/v3/orders/" + json.dumps(payload)
            signature = hmac.new(
                self.__api_secret.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Prepare headers
            headers = {
                "Authorization": f"Bitso {self.__api_key}:{nonce}:{signature}",
                "Content-Type": "application/json",
            }

            # Send the request
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            # Return the JSON response
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error submitting trade to Bitso API: {e}")
            return None


class BaseAsyncClient(threading.Thread):
    def __init__(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        pair: str,
    ):
        super().__init__()
        self.exchange = exchange
        self.pair = pair
        self.running = True
        self.ready = False
        self.__endpoint_url = "wss://ws.bitso.com"
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.__balance = {}
        self.__queue = None
        self.__orderbook_updater: OrderbookUpdater = None
        self.__order_submitter: OrderSubmitter = None
        self.__order_id_list = []
        self.__tradelist_updater: TradeListUpdater = None
        self.__tradelist = TradeList(exchange=self.exchange, pair=self.pair, trades=[])

    def __del__(self):
        self.stop()

    def stop(self):
        self.running = False
        self.__order_submitter.stop()
        self.__orderbook_updater.stop()
        self.__tradelist_updater.stop()
        self.__queue.put(None)
        self.__order_submitter.join()
        self.__orderbook_updater.join()
        self.__tradelist_updater.join()

    def run(self):
        self.__run()

    def submit_order(self, order: Order) -> None:
        self.__queue.put(Order)

    def get_orderbook(self) -> OrderBook:
        return self.__orderbook_updater.get_orderbook()

    def get_trades(self) -> TradeList:
        trades = self.__tradelist
        self.__tradeslist.trades.clear()
        return trades

    def get_balance(self) -> dict:
        return self.__balance

    def __run(self):

        self.__balance = self.__fetch_balance()
        self.__instantiate_subclasses()

        while self.running:
            self.__ready = True

            try:
                trade_or_order = self.__queue.get(block=True)
                if trade_or_order is None:
                    break

                if isinstance(trade_or_order, Trade):
                    # If we get a trade, we want to check whether the ID is in the list
                    trade_id = trade_or_order.id
                    if trade_id in self.__order_id_list:
                        self.__update_balance(trade_or_order)
                        # Add the trade to the tradelist
                    self.__tradelist.trades.append(trade_or_order)

                elif isinstance(trade_or_order, Order):

                    if self.__update_balance(trade_or_order):
                        self.__submit_order(
                            trade_or_order.side,
                            trade_or_order.amount,
                            trade_or_order.price,
                        )
                    else:
                        print(f"Error submitting order: {trade_or_order}")

                elif isinstance(trade_or_order, dict):

                    # If we get an order ID, add it to the list of order IDs to be checked against when receiving a trade so we can update the balance once that trade is fullfilled
                    self.__order_id_list.append()

                self.__queue.task_done()

            except Exception as e:
                print(f"Error in BaseAPI: {e}")
                traceback.print_exc()

        print("Stopped BaseAPI")

    def __instantiate_subclasses(self):
        self.__orderbook_updater = OrderbookUpdater(
            pair=self.pair,
            exchange_name=self.exchange,
            endpoint_url=self.__endpoint_url,
            subscription_payload={
                "action": "subscribe",
                "book": self.pair,
                "type": "orders",
            },
        )
        self.__queue = Queue()
        self.__tradelist_updater = TradeListUpdater(
            exchange_name=self.exchange,
            pair=self.pair,
            endpoint_url=self.__endpoint_url,
            subscription_payload={
                "action": "subscribe",
                "book": self.pair,
                "type": "trades",
            },
            order_id_queue=self.__queue,
        )

        self.__order_submitter = OrderSubmitter(
            exchange=self.exchange,
            api_key=self.__api_key,
            api_secret=self.__api_secret,
            pair=self.pair,
            order_id_queue=self.__queue,
        )
        # Start the updaters in separate threads
        threading.Thread(target=self.__orderbook_updater.run, daemon=True).start()
        threading.Thread(target=self.__tradelist_updater.run, daemon=True).start()
        threading.Thread(target=self.__order_submitter.run, daemon=True).start()

    def __update_balance(self, trade_or_order: Trade | Order) -> bool:
        base = "BTC"
        quote = "USDT"
        quote_amount = trade_or_order.price * trade_or_order.volume
        if isinstance(trade_or_order, Order):
            if trade_or_order.side == "buy":
                # Update balance for buy order
                if quote_amount <= self.__balance[quote]["free"]:
                    self.__balance[quote]["free"] -= quote_amount
                    self.__balance["free"][quote] = self.__balance[quote]["free"]
                    self.__balance[quote]["locked"] += quote_amount
                    return True
                else:
                    return False
            elif trade_or_order.side == "sell":
                # Update balance for sell order
                if trade_or_order.amount <= self.__balance[base]["free"]:
                    self.__balance[base]["free"] -= trade_or_order.amount
                    self.__balance["free"][base] = self.__balance[base]["free"]
                    self.__balance[base]["locked"] += trade_or_order.amount
                    return True
                else:
                    return False
            else:
                print(f"Unknown order side: {trade_or_order.side}")
                return False
        elif isinstance(trade_or_order, Trade):
            if trade_or_order.side == "buy":
                # Update balance for executed buy trade
                self.__balance[quote]["locked"] -= quote_amount
                self.__balance[base]["free"] += trade_or_order.amount
                self.__balance["free"][base] = self.__balance[base]["free"]
                return True
            elif trade_or_order.side == "sell":
                # Update balance for executed sell trade
                self.__balance[base]["locked"] -= trade_or_order.amount
                self.__balance[quote]["free"] += quote_amount
                self.__balance["free"][quote] = self.__balance[quote]["free"]
                return True
            else:
                print(f"Unknown trade side: {trade_or_order.side}")
                return False

        else:
            print(f"Unknown trade or order type: {type(trade_or_order)}")
            return False

    def __fetch_balance(self):
        try:
            # Bitso API endpoint for balance
            url = "https://api.bitso.com/v3/balance/"

            # Prepare the authentication
            nonce = str(int(time.time() * 1000))
            message = nonce + "GET" + "/v3/balance/"
            signature = hmac.new(
                self.__api_secret.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Prepare headers
            headers = {
                "Authorization": f"Bitso {self.__api_key}:{nonce}:{signature}",
                "Content-Type": "application/json",
            }

            # Make the request
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raises an HTTPError for bad responses

            data = response.json()

            if data["success"]:
                balances = data["payload"]["balances"]
                base = "BTC"
                quote = "USDT"

                for b in balances:
                    if b["currency"] == base.lower():
                        base_available = float(b["available"])
                        base_locked = float(b["locked"])
                    if b["currency"] == quote.lower():
                        quote_available = float(b["available"])
                        quote_locked = float(b["locked"])

                return {
                    base: {"free": base_available, "locked": base_locked},
                    quote: {"free": quote_available, "locked": quote_locked},
                    "free": {base: base_available, quote: quote_available},
                }

            else:
                print(f"Error in API response: {data['error']}")
                return None

        except Exception as e:
            print(f"Error fetching balance: {e}")
            traceback.print_exc()
            return None


class BitsoAPI(APIClient):

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.exchange_name = "bitso"
        super().__init__(api_key, api_secret, exchange_name=self.exchange_name)
        self.__client_list: dict[str, BaseAsyncClient] = {}
        self.__api_key = api_key
        self.__api_secret = api_secret

    def __del__(self):
        pass

    def stop(self):
        for client in self.__client_list:
            self.__client_list[client].stop()
        for client in self.__client_list:
            self.__client_list[client].join()

    def subscribe_pair(self, pair: str) -> None:
        if pair not in self.__client_list:
            self.__client_list.update(
                {
                    pair: BaseAsyncClient(
                        exchange=self.exchange_name,
                        api_key=self.__api_key,
                        api_secret=self.__api_secret,
                        pair=pair,
                    )
                }
            )

            threading.Thread(target=self.__client_list[pair].run, daemon=True).start()

    def get_order_book(self, pair: str) -> OrderBook | None:
        return self.__client_list[pair].get_orderbook()

    def get_trade_list(self, pair: str) -> TradeList | None:
        return self.__client_list[pair].get_trades()

    def get_balance(self, pair: str) -> dict:
        return self.__client_list[pair].get_balance()

    def create_order(self, symbol: str, order: Order):
        self.__client_list[pair].submit_order(Order)

    def cancel_order(self, symbol: str, order_id: str):
        pass

    def cancel_all_orders(self, symbol: str):
        pass

    def get_exchange_info(self):
        pass
