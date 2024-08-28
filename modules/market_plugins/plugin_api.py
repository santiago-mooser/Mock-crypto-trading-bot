from ..datamodel import OrderBook, TradeList, Order

class MethodNotDefined(Exception):
    def __init__(self, message="This method is not defined for the current API"):
        self.message = message
        super().__init__(self.message)

class APIClient:
    def __init__(self, api_key: str="", api_secret: str="", exchange_name: str=""):
        """
        Initialize the APIClient.

        This class serves as a base for implementing API clients for different exchanges.
        It provides a common interface for interacting with various cryptocurrency exchanges.

        Args:
            api_key (str): The API key for authentication with the exchange.
            api_secret (str): The API secret for authentication with the exchange.
            exchange_name (str): The name of the exchange this client is for.

        Attributes:
            api_key (str): The API key for authentication.
            api_secret (str): The API secret for authentication.

        Note:
            Subclasses should implement the abstract methods defined in this class
            to provide exchange-specific functionality.
        """
        self.__api_key = api_key
        self.__api_secret = api_secret

    def __del__(self):
        raise MethodNotDefined()

    def close(self):
        raise MethodNotDefined()

    def subscribe_pair(self, pair: str, depth: int):
        raise MethodNotDefined()

    def get_order_book(self, pair: str) -> OrderBook | None:
        raise MethodNotDefined()

    def get_trade_list(self, pair: str) -> TradeList | None:
        raise MethodNotDefined()

    def get_balance(self, pair: str):
        raise MethodNotDefined()

    def get_orders(self, pair: str):
        raise MethodNotDefined()

    def create_order(self, symbol: str, order: Order):
        raise MethodNotDefined()

    def cancel_order(self, symbol: str, order_id: str):
        raise MethodNotDefined()

    def cancel_all_orders(self, symbol: str):
        raise MethodNotDefined()

    def get_exchange_info(self):
        raise MethodNotDefined()
    