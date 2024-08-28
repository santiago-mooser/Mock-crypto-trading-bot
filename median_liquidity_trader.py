#!/usr/bin/env python3

from modules.market_plugins.bybit_ccxt import BybitAPI
from modules.market_plugins.bitso import BitsoAPI
from modules.strategies.arbitrage import arbitrager

import time
import os
import ujson as json


bybit_api_key = os.environ.get("BYBIT_API_KEY")
bybit_api_secret = os.environ.get("BYBIT_API_SECRET")

bitso_api_key = os.environ.get("BITSO_API_KEY")
bitso_api_secret = os.environ.get("BITSO_API_SECRET")


def MediaLiquidityTrader():

    bitso = BitsoAPI(api_key=bitso_api_key, api_secret=bitso_api_secret)
    bitso.subscribe_pair("btc_usdt")

    bybit = BybitAPI(api_key=bybit_api_key, api_secret=bybit_api_secret)
    bybit.subscribe_pair("BTC/USDT", 50)

    start_time = time.time()
    last_time = time.time()

    round_count = 0
    round_time = time.time()
    round_time_sum = 0

    volume = {
        "bitso": [0, 0, 0, 0, 0, 0],
        "bybit": [0, 0, 0, 0, 0, 0]
    }

    this_round = time.time()
    this_rounds = 0

    new_orders = []
    while True:
        try:
            orderbooks = []

            bybit_order_book = bybit.get_order_book("BTC/USDT")
            if bybit_order_book is not None:
                orderbooks.append(bybit_order_book)
            bitso_order_book = bitso.get_order_book("btc_usdt")
            if bitso_order_book is not None:
                orderbooks.append(bitso_order_book)

            balances = {
                "bybit": bybit.get_balance("BTC/USDT"),
                "bitso": bitso.get_balance("btc_usdt"),
            }

            orders = arbitrager(orderbooks, balances, symbol="BTC")
            # if orders is not None:
            #     new_orders.append(orders)
            # if orders is not an empty list
            if orders:
                new_orders.append(orders)

            round_count += 1
            this_rounds += 1
            round_time_sum += time.time() - round_time
            round_time = time.time()

            if time.time() - last_time >= 2:

                if len(new_orders) >=5 :
                    new_orders = new_orders[-10:]

                # clear the screen
                print("\033[H\033[J")

                print(
                    f"Time elapsed: {int((time.time() - start_time))}s\tRounds: {round_count}\tLast {this_rounds} rounds: {(time.time() - this_round)/this_rounds*1000*1000*1000}ns Average time per round: {round_time_sum / round_count*1000*1000*1000}ns"
                )

                if bybit_order_book is not None:
                    print(f"Bybit order book:")
                    print(
                        "{:^80}".format(
                            f"{bybit_order_book.bids[0].volume} {bybit_order_book.bids[0].price} - {bybit_order_book.asks[0].price} {bybit_order_book.asks[0].volume}"
                        )
                    )

                if bitso_order_book is not None:
                    print(f"bitso order book:")
                    print(
                        "{:^80}".format(
                            f"{bitso_order_book.bids[0].volume} {bitso_order_book.bids[0].price} - {bitso_order_book.asks[0].price} {bitso_order_book.asks[0].volume}"
                        )
                    )



                print(
                    "{:^80}".format(
                        f"Bybit Volume:\n\t\tBuy:\t\t{volume['bybit'][0]}BTC ${volume['bybit'][1]} {volume['bybit'][2]} trades\n\t\tSell:\t\t{volume['bybit'][3]}BTC ${volume['bybit'][4]} {volume['bybit'][5]} trades\n\t\tBalance:\t{balances['bybit']['BTC']['total']}BTC\t\t{balances['bybit']['USDT']['total']}USDT"
                    )
                )

                print(
                    "{:^80}".format(
                        f"bitso Volume:\n\t\tBuy:\t\t{volume['bitso'][0]}BTC ${volume['bitso'][1]} {volume['bitso'][2]} trades\n\t\tSell:\t\t{volume['bitso'][3]}BTC ${volume['bitso'][4]} {volume['bitso'][5]} trades\n\t\tBalance:\t{balances['bitso']['BTC']['free']+balances['bitso']['BTC']['locked']}BTC\t\t{balances['bitso']['USDT']['free']+balances['bitso']['BTC']['locked']}USDT"
                    )
                )

                print(f"Orders:")
                print(new_orders)


                last_time = time.time()

                this_round = time.time()
                this_rounds = 0

        except KeyboardInterrupt:
            bitso.stop()
            bybit.close()
            return 0


if __name__ == "__main__":
    # Create a new trader
    MediaLiquidityTrader()
