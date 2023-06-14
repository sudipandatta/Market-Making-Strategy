import requests
import json

class DeribitAPI:
    def __init__(self, api_key, api_secret, base_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    def _generate_signature(self, payload):
        # Generate signature for authenticated requests
        # Implement your own logic here
        pass

    def _send_request(self, method, endpoint, params=None, data=None):
        url = self.base_url + endpoint
        headers = {}

        if self.api_key and self.api_secret:
            headers['Authorization'] = 'Bearer ' + self.api_key

        if method == 'GET':
            response = requests.get(url, params=params, headers=headers)
        elif method == 'POST':
            headers['Content-Type'] = 'application/json'
            if data:
                data = json.dumps(data)
            response = requests.post(url, params=params, headers=headers, data=data)
        elif method == 'DELETE':
            response = requests.delete(url, params=params, headers=headers)
        else:
            raise ValueError('Invalid request method.')

        response_json = response.json()
        return response_json

    def send_order(self, instrument_name, side, quantity, price):
        endpoint = '/api/v1/trading/place_order'
        payload = {
            'instrument_name': instrument_name,
            'side': side,
            'quantity': quantity,
            'price': price
        }
        signature = self._generate_signature(payload)
        headers = {'X-Signature': signature}
        response = self._send_request('POST', endpoint, data=payload, headers=headers)
        return response

    def update_order(self, order_id, price, quantity):
        endpoint = '/api/v1/trading/modify'
        payload = {
            'order_id': order_id,
            'price': price,
            'quantity': quantity
        }
        signature = self._generate_signature(payload)
        headers = {'X-Signature': signature}
        response = self._send_request('POST', endpoint, data=payload, headers=headers)
        return response

    def cancel_order(self, order_id):
        endpoint = '/api/v1/trading/cancel'
        payload = {
            'order_id': order_id
        }
        signature = self._generate_signature(payload)
        headers = {'X-Signature': signature}
        response = self._send_request('POST', endpoint, data=payload, headers=headers)
        return response

    def get_order_execution_update(self, order_id):
        endpoint = '/api/v1/trading/order_state'
        params = {'order_id': order_id}
        response = self._send_request('GET', endpoint, params=params)
        return response

    def get_live_market_quotes(self, instrument_name):
        endpoint = '/api/v1/public/ticker'
        params = {'instrument_name': instrument_name}
        response = self._send_request('GET', endpoint, params=params)
        if 'result' in response:
            bid_price = response['result']['bid'][1]
            ask_price = response['result']['ask'][1]
            return bid_price, ask_price
        else:
            return None, None

    def get_option_chain_instruments(self, underlying, expiry):
        endpoint = '/api/v1/public/get_instruments'
        params = {
            'currency': underlying,
            'expired': False,
            'expired_testnet': False
        }
        response = self._send_request('GET', endpoint, params=params)
        instruments = []

        if 'result' in response:
            for instrument in response['result']:
                if instrument['kind'] == 'option' and instrument['expiration_timestamp'] == expiry:
                    instruments.append({
                        'instrument_name': instrument['instrument_name'],
                        'kind': 'option',
                        'strike': instrument['strike'],
                        'option_type': instrument['option_type']
                    })
                elif instrument['kind'] == 'future':
                    instruments.append({
                        'instrument_name': instrument['instrument_name'],
                        'kind': 'future',
                        'expiry': instrument['expiration_timestamp']
                    })

        return instruments
