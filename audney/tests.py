from django.urls import reverse
from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from .market_analysis import get_stock_price, extract_company_name, get_ticker_symbol_from_name
from .financial_statistics import extract_location
from django.contrib.auth.models import User
import json

class ExtractCompanyNameTestCase(TestCase):
    @patch('audney.market_analysis.client.chat.completions.create')  # Corrected patch path
    def test_extract_company_name(self, mock_openai_create):
        # Mock the OpenAI API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='Apple'))]
        mock_openai_create.return_value = mock_response

        # Test the function
        result = extract_company_name("What is the price of Apple?")
        self.assertEqual(result, 'Apple', "Should extract 'Apple' as the company name")


class TestStockPriceQuery(TestCase):
    @patch('audney.market_analysis.requests.get')
    def test_clorox_ticker_and_stock_price(self, mock_get):
        mock_response_ticker = MagicMock()
        mock_response_price = MagicMock()

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

        mock_get.side_effect = [mock_response_ticker, mock_response_price]

        ticker = get_ticker_symbol_from_name("Clorox Company")
        self.assertEqual(ticker, [('Clorox Company', 'CLX')], "Ticker symbol should be CLX for Clorox Company")

        stock_price = get_stock_price('CLX')
        self.assertEqual(stock_price, "$145.50", "Stock price should be $145.50 for CLX")

class ExtractLocationTestCase(TestCase):
    @patch('audney.financial_statistics.client.chat.completions.create')  # Mock OpenAI for location extraction
    def test_extract_location(self, mock_openai_create):
        # Mock the OpenAI API response to return proper locations in "City, State" format
        mock_response = MagicMock()
        mock_openai_create.return_value = mock_response

        test_cases = [
            ("Can you give me some employment data for Denver, CO?", "Denver", "CO"),
            ("What's the unemployment rate in New York, NY?", "New York", "NY"),
            ("Tell me about housing in Los Angeles, CA", "Los Angeles", "CA"),
            ("What's the weather like in Miami, FL?", "Miami", "FL"),
            ("Provide data for Chicago, IL", "Chicago", "IL"),
            ("Any news in Boston, MA?", "Boston", "MA"),
            ("I want info on Seattle, WA", "Seattle", "WA"),
            ("How's life in Austin, TX?", "Austin", "TX"),
            ("Can you give me some data for San Francisco, CA?", "San Francisco", "CA"),
            ("Tell me about life in Portland, OR", "Portland", "OR"),
            # Cases where no location is given in input but should be pulled from profile
            ("Can you give me some employment data?", "Sacramento", "CA"),
            ("What's the unemployment rate?", "Sacramento", "CA"),
        ]

        user_profile = {"city": "Sacramento", "state": "CA"}  # Test with a dummy user profile

        for input_text, expected_city, expected_state in test_cases:
            # Adjust the mocked response content to return the expected city and state
            mock_response.choices[0].message.content = f"{expected_city}, {expected_state}"
            with self.subTest(input_text=input_text):
                city, state = extract_location(input_text, user_profile)
                self.assertEqual(city, expected_city, f"Expected city '{expected_city}' but got '{city}'")
                self.assertEqual(state, expected_state, f"Expected state '{expected_state}' but got '{state}'")
            