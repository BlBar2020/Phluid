from django.urls import path
from django.test import TestCase
from .market_analysis import get_stock_price, extract_stock_symbol
from unittest.mock import patch
from django.urls import reverse
from django.test import Client
from .views import chatbot_response




class MarketAnalysisTestCase(TestCase):
    def test_get_stock_price(self):
        price = get_stock_price("AAPL")
        self.assertIsNotNone(price)


class ExtractStockSymbolTestCase(TestCase):
    def test_extract_stock_symbol(self):
        self.assertEqual(extract_stock_symbol(
            "What is Price of AAPL?"), "AAPL")
        self.assertEqual(extract_stock_symbol(
            "What is the price of MSFT?"), "MSFT")
        self.assertIsNone(extract_stock_symbol(
            "Tell me about the stock market"))
        # Add more test cases as necessary


class ChatbotResponseTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('audney.views.extract_stock_symbol')
    def test_price_request(self, mock_extract_stock_symbol):
        # Setup mock behavior for symbol extraction
        mock_extract_stock_symbol.return_value = 'AAPL'

        # Simulate a GET request
        response = self.client.get(reverse('chatbot_response'), {
                                   'message': 'What is the price of AAPL?'})  # Adjust URL

        # Since the actual stock price can vary, you might check if the response
        # format is as expected rather than a fixed price
        self.assertIn('The price of AAPL is ', response.content.decode())
