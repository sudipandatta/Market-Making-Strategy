import requests
import json
import py_vollib.black_scholes.implied_volatility as bs_iv
import py_vollib.black_scholes.greeks.analytical as bs_greeks
import time

class TradeData:
    def __init__(self):
        self.market_quotes = {}
        self.underlying_future_bid = 0
        self.underlying_future_ask = 0
        self.positions = {}
        self.active_orders = {}
        self.underlying_future_name = None
        self.instrument_list = []

        self.portfolio_delta = 0
        self.portfolio_vega = 0
        self.portfolio_gamma = 0

    def initialize_position(self, instrument, risk_free_rate):
        self.instrument_list.append('instrument_name')
        if instrument['kind'] == 'future':
            self.underlying_future_name = instrument['instrument_name']
            self.positions[instrument['instrument_name']] = Position(instrument['instrument_name'], None, None, instrument['expiry'], risk_free_rate)
        else:
            self.positions[instrument['instrument_name']] = Position(instrument['instrument_name'], instrument['strike'], instrument['option_type'], instrument['expiry'], risk_free_rate)

    def update_market_quotes(self, instrument_name, bid_price, ask_price):
        if self.underlying_future_name != instrument_name:
            self.market_quotes[instrument_name] = (bid_price, ask_price)
            self.positions[instrument_name].calculate_option_greeks(bid_price, ask_price, (self.underlying_future_ask + self.underlying_future_bid) / 2)
        else:
            self.underlying_future_bid, self.underlying_future_ask = bid_price, ask_price

    def update_active_orders(self, instrument_name, active_buy_order, active_sell_order):
        self.active_orders[instrument_name] = {
            'buy_order': active_buy_order,
            'sell_order': active_sell_order
        }

    def calculate_realized_pnl(self):
        realized_pnl = 0
        for position in self.positions.values():
            realized_pnl += position.calculate_realized_pnl()
        return realized_pnl

    def calculate_unrealized_pnl(self):
        unrealized_pnl = 0
        for instrument_name, position in self.positions.items():
            if instrument_name in self.market_quotes:
                bid_price, ask_price = self.market_quotes[instrument_name]
                unrealized_pnl += position.calculate_unrealized_pnl(bid_price, ask_price)
        return unrealized_pnl

    def get_portfolio_pnl(self):
        realized_pnl = self.calculate_realized_pnl()
        unrealized_pnl = self.calculate_unrealized_pnl()
        portfolio_pnl = realized_pnl + unrealized_pnl
        return realized_pnl, unrealized_pnl, portfolio_pnl

    def order_execute(self, instrument, quantity, price):
        if instrument == self.underlying_future_name:
            self.positions[instrument].update_position(quantity, price)
            if quantity > 0:
                self.portfolio_delta += quantity
            else:
                self.portfolio_delta -= quantity

        else:
            self.portfolio_delta -= (self.positions[instrument].delta * self.positions[instrument].quantity)
            self.portfolio_gamma -= (self.positions[instrument].gamma * self.positions[instrument].quantity)
            self.portfolio_vega -= (self.positions[instrument].vega * self.positions[instrument].quantity)

            self.positions[instrument].update_position(quantity, price)

            self.portfolio_delta += (self.positions[instrument].delta * self.positions[instrument].quantity)
            self.portfolio_gamma += (self.positions[instrument].gamma * self.positions[instrument].quantity)
            self.portfolio_vega += (self.positions[instrument].vega * self.positions[instrument].quantity)

class Position:
    def __init__(self, instrument_name, strike, typ, expiry, risk_free_rate):
        self.instrument_name = instrument_name
        self.strike = strike
        self.typ = typ
        self.expiry = expiry
        self.risk_free_rate = risk_free_rate
        self.time_to_expiry = 0

        self.quantity = 0
        self.tot_buy_cost = 0
        self.total_buys = 0
        self.avg_buy_price = 0
        self.total_sell_cost = 0
        self.total_sells = 0
        self.avg_sell_price = 0

        self.iv = 0
        self.delta = 0
        self.gamma = 0
        self.theta = 0
        self.vega = 0
        self.rho = 0

    def update_position(self, quantity, price):
        if quantity > 0:
            self.total_buys += quantity
            self.tot_buy_cost += quantity * price
            self.avg_buy_price = self.tot_buy_cost / self.total_buys
        else:
            self.total_sells += abs(quantity)
            self.total_sell_cost += abs(quantity) * price
            self.avg_sell_price = self.total_sell_cost / self.total_sells
        self.quantity += quantity

    def calculate_realized_pnl(self):
        min_quantity = min(self.total_buys, self.total_sells)
        pnl = min_quantity * (self.avg_sell_price - self.avg_buy_price)
        return pnl

    def calculate_unrealized_pnl(self, bid_price, ask_price):
        fair_price = (bid_price + ask_price) / 2
        net_quantity = self.total_buys - self.total_sells
        if net_quantity > 0:
            pnl = abs(net_quantity) * (fair_price - self.avg_buy_price)
        else:
            pnl = abs(net_quantity) * (self.avg_sell_price - fair_price)
        return pnl
    
    def calculate_option_greeks(self, bid_price, ask_price, underlying_price):
        self.time_to_expiry = (self.expiry - time.time()) / (365 * 24 * 60 * 60)
        self.mid_price = (bid_price + ask_price) / 2
        self.iv = bs_iv.implied_volatility(self.mid_price, underlying_price, self.strike, self.time_to_expiry, self.risk_free_rate, self.typ)
        self.delta = bs_greeks.delta(self.typ, underlying_price, self.strike, self.time_to_expiry, self.risk_free_rate, self.iv)
        self.gamma = bs_greeks.gamma(self.typ, underlying_price, self.strike, self.time_to_expiry, self.risk_free_rate, self.iv)
        self.theta = bs_greeks.theta(self.typ, underlying_price, self.strike, self.time_to_expiry, self.risk_free_rate, self.iv)
        self.vega = bs_greeks.vega(self.typ, underlying_price, self.strike, self.time_to_expiry, self.risk_free_rate, self.iv)
        self.rho = bs_greeks.rho(self.typ, underlying_price, self.strike, self.time_to_expiry, self.risk_free_rate, self.iv)
