from ..datamodel import OrderBook, Order

fees = {"kraken": 0.001, "bitso": 0.00099, "bybit": 0.0006, "gate.io": 0.001}

def arbitrager(
    orderbooks: list[OrderBook], balances: dict[str, float], symbol: str
) -> list[dict[str, dict[str, float]]]:
    trades = []

    for i, orderbook in enumerate(orderbooks):
        if orderbook is None:
            return None
        if i == len(orderbooks) - 1:
            break

        USDT_balance = balances[orderbook.exchange].get("free", {}).get("USDT", 0.0)
        symbol_balance = (
            balances[orderbooks[i + 1].exchange].get("free", {}).get(symbol, 0.0)
        )
        bids_done = False
        for bid in orderbook.bids:
            for ask in orderbooks[i + 1].asks:

                if bid.price <= ask.price:
                    bids_done = True
                    break

                trade_volume = min(
                    bid.volume, ask.volume, USDT_balance / ask.price, symbol_balance
                )

                if trade_volume <= 0:
                    continue
                # calculate potential profit
                profit = (ask.price - bid.price) * trade_volume - (trade_volume * bid.price * fees[orderbook.exchange]) - (trade_volume * ask.price * fees[orderbooks[i + 1].exchange])
                if profit <= 0:
                    continue
                trades.append(
                    Order(
                        price=bid.price,
                        volume=trade_volume,
                        exchange=orderbook.exchange,
                        side="sell",
                    )
                )
                trades.append(
                    Order(
                        price=ask.price,
                        volume=trade_volume,
                        exchange=orderbooks[i + 1].exchange,
                        side="buy",
                    )
                )
                balances[orderbook.exchange]["USDT"]["free"] += trade_volume / ask.price
                balances[orderbook.exchange][symbol]["free"] -= trade_volume

                balances[orderbooks[i + 1].exchange]["USDT"]["free"] -= (
                    trade_volume / ask.price
                )
                balances[orderbooks[i + 1].exchange][symbol]["free"] += trade_volume

            if bids_done:
                bids_done = False
                break

        for ask in orderbook.asks:
            for bid in orderbooks[i + 1].asks:

                if bid.price <= ask.price:
                    bids_done = True
                    break

                trade_volume = min(
                    bid.volume, ask.volume, USDT_balance / ask.price, symbol_balance
                )
                if trade_volume <= 0:
                    continue
                profit = (ask.price - bid.price) * trade_volume - (ask.price * trade_volume * fees[orderbook.exchange]) - (bid.price * trade_volume * fees[orderbooks[i + 1].exchange])
                if profit <= 0:
                    continue
                trades.append(
                    Order(
                        price=ask.price,
                        volume=trade_volume,
                        exchange=orderbook.exchange,
                        side="sell",
                    )
                )
                trades.append(
                    Order(
                        price=bid.price,
                        volume=trade_volume,
                        exchange=orderbooks[i + 1].exchange,
                        side="buy",
                    )
                )
                balances[orderbook.exchange]["USDT"]["free"] -= trade_volume / ask.price
                balances[orderbook.exchange][symbol]["free"] += trade_volume

                balances[orderbooks[i + 1].exchange]["USDT"]["free"] += (
                    trade_volume / ask.price
                )
                balances[orderbooks[i + 1].exchange][symbol]["free"] -= trade_volume

            if bids_done:
                bids_done = False
                break

        return trades
