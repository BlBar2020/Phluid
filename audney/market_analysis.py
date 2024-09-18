# Import necessary modules
import os
from .models import MarketCondition
import pandas as pd
import numpy as np
import logging
from datetime import datetime as dt, date, timedelta
import requests
from django.conf import settings
from openai import OpenAI
import polygon
import yfinance as yf
import json

# Get the OpenAI and Polygon API keys from settings
openai_api_key = settings.OPENAI_API_KEY
polygon_api_key = settings.POLYGON_API_KEY

# Get the logger for this module
logger = logging.getLogger(__name__)

# Function to calculate user's age from their date of birth
def calculate_user_age(date_of_birth):
    try:
        if not date_of_birth:
            return None
        today = date.today()
        age = today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
        return age
    except Exception as e:
        logger.error(f"Error calculating age: {e}")
        return None

def get_stock_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            formatted_price = "${:.2f}".format(price)
            return formatted_price
        else:
            return f"Stock data not available for {ticker_symbol}. It may be inactive or delisted."
    except Exception as e:
        logger.error(f"Error fetching stock price for {ticker_symbol}: {e}")
        return f"Error fetching stock price: {e}"

def classify_market(row, threshold=0.20):
    try:
        if row >= threshold:
            return 'Bull'
        elif row <= -threshold:
            return 'Bear'
        else:
            return 'Neutral'
    except Exception as e:
        logger.error(f"Error classifying market: {e}")
        return 'Unknown'

def update_market_conditions():
    try:
        tickers = ['TQQQ', 'SPY', 'X:BTCUSD']
        current_datetime = dt.now()

        # Define the start and end dates for the last five years
        start_date = current_datetime - timedelta(days=5 * 365)
        end_date = current_datetime

        for ticker in tickers:
            # Fetch data using yfinance
            data = yf.download(ticker, start=start_date, end=end_date)

            if not data.empty:
                # Ensure the 'Close' column is available
                data = data[['Close']]

                # Calculate daily returns
                data['Returns'] = data['Close'].pct_change().fillna(0)

                # Calculate cumulative returns
                data['Cumulative_Returns'] = (1 + data['Returns']).cumprod() - 1

                # Classify the market based on the latest cumulative return
                latest_cumulative_return = data['Cumulative_Returns'].iloc[-1]
                current_market_condition = classify_market(latest_cumulative_return)
                
                # Update or create the market condition in the database
                MarketCondition.objects.update_or_create(ticker=ticker, defaults={'condition': current_market_condition})
            else:
                logger.error(f"No data returned for ticker {ticker}.")
    except Exception as e:
        logger.error(f"Error updating market conditions: {e}")


def extract_stock_symbol_with_nlp(text):
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        messages = [
            {"role": "system", "content": "Identify the most relevant company and its stock symbol from the text."},
            {"role": "user", "content": text}
        ]
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        extracted_info = response.choices[0].message['content'].strip()
        return extracted_info
    except Exception as e:
        logger.error(f"Error in NLP extraction with chat model: {e}")
        return None

# Function to get ticker symbol from a company name
def get_ticker_symbol_from_name(company_name):
    try:
        url = f"https://api.polygon.io/v3/reference/tickers?search={company_name}&active=true&sort=ticker&order=asc&limit=10&apiKey={polygon_api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            matches = [(ticker_info.get('name', ''), ticker_info.get('ticker', '')) for ticker_info in data.get('results', [])]
            return matches
        else:
            logger.error(f"Error fetching ticker symbol for company name {company_name}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error in get_ticker_symbol_from_name function: {e}")
        return []

# Function to extract a company name from a text string
# Function to extract a clean company name or ticker symbol from user input
def extract_company_name(text):
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        if not text:
            logger.warning("Input text is empty.")
            return None

        messages = [
            {"role": "system", "content": "Extract the company name or ticker symbol from the text."},
            {"role": "user", "content": text}
        ]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )

        if response.choices:
            message_content = response.choices[0].message.content.strip()
            logger.info(f"Extracted company name or ticker symbol: {message_content}")
            
            # Ensure we return only the name or ticker, not a descriptive string
            extracted_text = message_content.split(':')[-1].strip()  # Assume format is "Company name: Apple"
            return extracted_text
        else:
            logger.warning("No company name or ticker symbol found.")
            return None

    except Exception as e:
        logger.error(f"Failed to extract company name: {e}")
        return None

# Function to search for a company or ticker symbol with prioritized matches
def search_company_or_ticker(query):
    try:
        # Ensure the extracted query is valid and clean
        extracted_query = extract_company_name(query)
        if not extracted_query:
            return []
        
        # Send the cleaned-up query to the Polygon API
        url = f"https://api.polygon.io/v3/reference/tickers?search={extracted_query}&apiKey={polygon_api_key}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Filter the results based on whether the company name or ticker symbol contains the query (case-insensitive)
            possible_matches = [
                (result['name'], result['ticker']) 
                for result in data.get('results', []) 
                if extracted_query.lower() in result['name'].lower() or extracted_query.lower() in result['ticker'].lower()
            ]
            
            # Return an exact match if one exists, otherwise return the filtered possible matches
            exact_matches = [match for match in possible_matches if extracted_query.lower() == match[0].lower()]

            if len(exact_matches) == 1:
                return exact_matches[0]  # Return the exact match
            return possible_matches if possible_matches else []
        else:
            logger.error(f"Error searching for company/ticker: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error searching for company/ticker: {e}")
        return []

# Function to handle stock price queries
def handle_stock_price_query(user_input):
    company_name_or_symbol = extract_company_name(user_input)
    possible_matches = search_company_or_ticker(company_name_or_symbol)

    if isinstance(possible_matches, tuple):
        # Only one result, return stock price
        company_name, ticker_symbol = possible_matches
        stock_price = get_stock_price(ticker_symbol)
        response_message = f"Currently, {company_name} ({ticker_symbol}) is priced at {stock_price}."
        contains_html = False
    else:
        # Multiple matches or no match
        if len(possible_matches) > 1:
            response_message = "I found multiple companies with that name, please choose the one you're referring to: "
            response_message += "<ul>"
            for name, ticker in possible_matches:
                response_message += f"<li><a href='#' onclick='fetchStockPrice(\"{ticker}\", \"{name}\")'>{name} ({ticker})</a></li>"
            response_message += "</ul>"
            contains_html = True
        else:
            response_message = "Sorry, I couldn't find the stock price for the company you mentioned."
            contains_html = False

    return response_message, contains_html