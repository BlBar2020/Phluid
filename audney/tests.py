import os
import requests
from django.urls import reverse
from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from .market_analysis import get_stock_price, extract_company_name, get_ticker_symbol_from_name
from .views import ask_openai
from django.contrib.auth.models import User


class MarketAnalysisTestCase(TestCase):
    def test_get_stock_price(self):
        price = get_stock_price("AAPL")
        self.assertIsNotNone(price)


class ExtractCompanyNameTestCase(TestCase):
    @patch('audney.market_analysis.extract_company_name')
    def test_extract_company_name(self, mock_extract_company_name):
        # Mocking the function to return 'Apple' directly
        mock_extract_company_name.return_value = 'Apple'
        
        self.assertEqual(extract_company_name("What is the price of Apple?"), 'Apple')


class ChatbotResponseTest(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='testuser', password='password')

    @patch('audney.financial_statistics.get_census_data_msa_or_place')
    @patch('audney.query_handlers.handle_stock_price_query')
    def test_price_request(self, mock_handle_stock_price_query, mock_get_census_data):
        mock_get_census_data.return_value = 60000  # Mock income value

        self.client.login(username='testuser', password='password')
        
        response = self.client.get(reverse('chatbot_response'), {'message': 'What is the price of AAPL?'})
        
        # Check that the response includes multiple options for Apple Inc
        self.assertIn("multiple companies with that name", response.content.decode())
        self.assertIn("Apple Inc", response.content.decode())


class TestStockPriceQuery(TestCase):
    @patch('audney.market_analysis.requests.get')
    def test_clorox_ticker_and_stock_price(self, mock_get):
        # Mock the responses
        mock_response_ticker = MagicMock()
        mock_response_price = MagicMock()

        # Set up the mock response for SYMBOL_SEARCH
        mock_ticker_data = {
            "bestMatches": [
                {
                    "1. symbol": "CLX",
                    "2. name": "Clorox Company",
                    "3. type": "Equity",
                    "4. region": "United States",
                    "5. marketOpen": "09:30",
                    "6. marketClose": "16:00",
                    "7. timezone": "UTC-05",
                    "8. currency": "USD",
                    "9. matchScore": "1.0000"
                }
            ]
        }
        mock_response_ticker.status_code = 200
        mock_response_ticker.json.return_value = mock_ticker_data
        
        # Mock response for stock price API
        mock_stock_price_data = {
            "Time Series (5min)": {
                "2024-10-07 16:00:00": {
                    "1. open": "145.00",
                    "2. high": "146.00",
                    "3. low": "144.50",
                    "4. close": "145.50",
                    "5. volume": "1200000"
                }
            }
        }
        mock_response_price.status_code = 200
        mock_response_price.json.return_value = mock_stock_price_data

        # Chain the responses in the order they will be called
        mock_get.side_effect = [mock_response_ticker, mock_response_price]

        # Step 1: Get ticker symbol from company name
        ticker = get_ticker_symbol_from_name("Clorox Company")
        self.assertEqual(ticker, [('Clorox Company', 'CLX')], "Ticker symbol should be CLX for Clorox Company")
        
        # Step 2: Get stock price using the ticker
        stock_price = get_stock_price('CLX')
        self.assertEqual(stock_price, "$145.50", "Stock price should be $145.50 for CLX")