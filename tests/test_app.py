import os
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_temp = tempfile.TemporaryDirectory()
os.environ['SUSHIWAVE_DB'] = os.path.join(_temp.name, 'test.db')
from app import app, db  # noqa: E402


class SushiWaveTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['csrf_token'] = 'test-csrf'
        self.headers = {'X-CSRF-Token': 'test-csrf'}

    def payload(self):
        when = datetime.now(ZoneInfo('Europe/Kyiv')) + timedelta(days=1)
        when = when.replace(hour=12, minute=0, second=0, microsecond=0)
        return {'name': 'Тестовий покупець', 'phone': '+380991234567', 'pickup_at': when.strftime('%Y-%m-%dT%H:%M'),
                'items': [{'id': 1, 'quantity': 2, 'modifiers': [1]}], 'comment': ''}

    def test_catalog_has_26_products(self):
        data = self.client.get('/api/menu').get_json()
        self.assertEqual(len(data['products']), 26)

    def test_valid_order_and_server_price(self):
        payload = self.payload()
        payload['total'] = 1  # client-supplied price must be ignored
        resp = self.client.post('/api/orders', json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertEqual(resp.get_json()['total'], (289+20)*2)
        self.assertEqual(self.client.get(resp.get_json()['tracking_url']).status_code, 200)

    def test_reject_negative_quantity(self):
        p = self.payload(); p['items'][0]['quantity'] = -2
        resp = self.client.post('/api/orders', json=p, headers=self.headers)
        self.assertEqual(resp.status_code, 400)

    def test_reject_unavailable_product(self):
        with app.app_context():
            db().execute('UPDATE products SET available=0 WHERE id=1'); db().commit()
        try:
            resp = self.client.post('/api/orders', json=self.payload(), headers=self.headers)
            self.assertEqual(resp.status_code, 400)
        finally:
            with app.app_context():
                db().execute('UPDATE products SET available=1 WHERE id=1'); db().commit()

    def test_requires_csrf(self):
        resp = self.client.post('/api/orders', json=self.payload())
        self.assertEqual(resp.status_code, 403)

    def test_operator_redirect_when_unauthorized(self):
        self.assertEqual(self.client.get('/operator').status_code, 302)

    def test_reject_invalid_pickup(self):
        p = self.payload(); p['pickup_at'] = '2020-01-01T12:00'
        self.assertEqual(self.client.post('/api/orders', json=p, headers=self.headers).status_code, 400)


if __name__ == '__main__':
    unittest.main()
