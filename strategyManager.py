import time
from marketOrderManager import DeribitAPI
from tradeDataManager import TradeData, Position
import tradeDataManager
import threading

class DeltaNeutralMarketMaker:
    def __init__(self, api_key, api_secret, base_url, underlying, expiry, risk_free_rate, open_position_limit, order_size, delta_limit, gamma_limit, vega_limit):
        self.deribit_api = DeribitAPI(api_key, api_secret, base_url)
        self.trade_data = TradeData()
        self.underlying = underlying
        self.expiry = expiry
        self.risk_free_rate = risk_free_rate
        self.open_position_limit = open_position_limit
        self.order_size = order_size
        self.delta_limit = delta_limit
        self.gamma_limit = gamma_limit
        self.vega_limit = vega_limit

    def run_strategy(self):
        instruments = self.deribit_api.get_option_chain_instruments(self.underlying, self.expiry)

        for instrument in instruments:
            self.trade_data.initialize_position(instrument)

        market_quotes_thread = threading.Thread(target=self.update_market_quotes_thread)
        order_updates_thread = threading.Thread(target=self.receive_order_updates_thread)
        risk_management_thread = threading.Thread(target=self.risk_management_thread)

        market_quotes_thread.start()
        order_updates_thread.start()
        risk_management_thread.start()

    def update_market_quotes_thread(self):
        while True:
            for instrument in self.trade_data.positions.keys():
                bid_price, ask_price = self.deribit_api.get_live_market_quotes(instrument)
                if bid_price is not None and ask_price is not None:
                    self.trade_data.update_market_quotes(instrument, bid_price, ask_price)


    def receive_order_updates_thread(self):
        while True:
            for instrument in self.trade_data.positions.keys():
                if self.trade_data.active_orders[instrument]['buy_order'] is not None:
                    execution_update = self.deribit_api.get_order_execution_update(self.trade_data.active_orders[instrument]['buy_order'])
                    if execution_update['order_state'] == 'filled':
                        quantity = self.trade_data.active_orders[instrument]['buy_order']['quantity']
                        price = self.trade_data.active_orders[instrument]['buy_order']['price']
                        self.trade_data.order_execute(instrument, quantity, price)
                        self.trade_data.update_active_orders(instrument, None, self.trade_data.active_orders[instrument]['sell_order'])

                if self.trade_data.active_orders[instrument]['sell_order'] is not None:
                    execution_update = self.deribit_api.get_order_execution_update(self.trade_data.active_orders[instrument]['sell_order'])
                    if execution_update['order_state'] == 'filled':
                        quantity = -1 * self.trade_data.active_orders[instrument]['sell_order']['quantity']
                        price = self.trade_data.active_orders[instrument]['sell_order']['price']
                        self.trade_data.order_execute(instrument, quantity, price)
                        self.trade_data.update_active_orders(instrument, self.trade_data.active_orders[instrument]['buy_order'], None)


    def risk_management_thread(self):
        while True:
            for instrument in self.trade_data.positions.keys():
                if instrument == self.trade_data.underlying_future_name:
                    continue
                current_position = self.trade_data.positions[instrument].quantity
                current_market_bid = self.trade_data.market_quotes[instrument]['bid']
                current_market_ask = self.trade_data.market_quotes[instrument]['ask']
                current_buy_order = self.trade_data.active_orders[instrument]['buy_order']
                current_sell_order = self.trade_data.active_orders[instrument]['sell_order']

                if not self.is_risk_limit_hit(instrument, self.order_size, current_market_bid):
                    if current_buy_order is not None and current_buy_order['price'] != current_market_bid:
                        self.deribit_api.update_order(current_buy_order['order_id'], self.order_size, current_market_bid)
                        current_buy_order['price'] = current_market_bid
                    elif current_buy_order == None:
                        response = self.deribit_api.send_order(instrument, 'buy', self.order_size, current_market_bid)
                        current_buy_order = {
                            'order_id': response['result']['order']['order_id'],
                            'price': current_market_bid,
                            'quantity': self.order_size
                        }
                else:
                    if current_buy_order is not None:
                        self.deribit_api.cancel_order(current_buy_order['order_id'])
                        current_buy_order = None
                
                if not self.is_risk_limit_hit(instrument, -1 * self.order_size, current_market_ask):
                    if current_sell_order is not None and current_sell_order['price'] != current_market_ask:
                        self.deribit_api.update_order(current_sell_order['order_id'], self.order_size, current_market_ask)
                        current_sell_order['price'] = current_market_ask
                    elif current_sell_order == None:
                        response = self.deribit_api.send_order(instrument, 'sell', self.order_size, current_market_ask)
                        current_sell_order = {
                            'order_id': response['result']['order']['order_id'],
                            'price': current_market_ask,
                            'quantity': self.order_size
                        }
                else:
                    if current_sell_order is not None:
                        self.deribit_api.cancel_order(current_sell_order['order_id'])
                        current_sell_order = None

                self.trade_data.active_orders[instrument] = {current_buy_order, current_sell_order}

                # Send, modify or cancel future hedge orders
                # TODO: Implement hedge orders with futures
                

    def is_risk_limit_hit(self, instrument, quantity):
        
        risk_limit_hit = False

        instrument_delta = self.trade_data.positions[instrument].delta * quantity
        instrument_gamma = self.trade_data.positions[instrument].gamma * quantity
        instrument_vega = self.trade_data.positions[instrument].vega * quantity

        if self.portfolio_delta * instrument_delta > 0 and abs(self.portfolio_delta + instrument_delta) > self.delta_limit: risk_limit_hit = True
        if self.portfolio_gamma * instrument_gamma > 0 and abs(self.portfolio_gamma + instrument_gamma) > self.gamma_limit: risk_limit_hit = True
        if self.portfolio_vega * instrument_vega > 0 and abs(self.portfolio_vega + instrument_vega) > self.vega_limit: risk_limit_hit = True
        if self.positions[instrument].quantity + quantity > self.open_position_limit: risk_limit_hit = True

        return risk_limit_hit


# Usage Example:
api_key = 'YOUR_API_KEY'
api_secret = 'YOUR_API_SECRET'
base_url = 'https://test.deribit.com'  # Replace with the appropriate base URL
underlying = 'ETH-USD'
expiry = 1672502400  # Unix timestamp for the expiry date (e.g., Jun 2023)
risk_free_rate = 0
open_position_limit = 4
order_size = 1
vega_limit = 1000
gamma_limit = 1000
delta_limit = 100000
market_maker = DeltaNeutralMarketMaker(api_key, api_secret, base_url, underlying, expiry, risk_free_rate, open_position_limit, order_size, delta_limit, gamma_limit, vega_limit)
market_maker.run_strategy()
