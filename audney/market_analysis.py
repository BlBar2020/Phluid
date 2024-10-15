# Import necessary modules
import os
from .models import MarketCondition
import pandas as pd
import logging
from datetime import datetime as dt, date, timedelta
import requests
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Get the logger for this module
logger = logging.getLogger(__name__)

# Set the OpenAI API key globally


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
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            logger.error("Alpha Vantage API key not found in environment variables.")
            return "Error fetching stock price: API key not found."

        logger.info(f"Fetching stock price for ticker: {ticker_symbol}")

        # Make API call to Alpha Vantage for the stock price
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker_symbol}&interval=5min&apikey={api_key}'
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Extract the latest closing price from the API response
            time_series = data.get('Time Series (5min)', {})
            if time_series:
                latest_timestamp = max(time_series.keys())
                price = time_series[latest_timestamp]['4. close']
                formatted_price = "${:.2f}".format(float(price))
                logger.info(f"Retrieved stock price for {ticker_symbol}: {formatted_price}")
                return formatted_price
            else:
                logger.warning(f"No stock data available for {ticker_symbol}. It may be inactive or delisted.")
                return f"Stock data not available for {ticker_symbol}. It may be inactive or delisted."
        else:
            logger.error(f"Error fetching stock price from Alpha Vantage: {response.text}")
            return f"Error fetching stock price: {response.status_code}"

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
        tickers = ['TQQQ', 'SPY', 'CLX']  # Example tickers
        current_datetime = dt.now()

        # Define the start and end dates for the last five years
        start_date = current_datetime - timedelta(days=5 * 365)
        end_date = current_datetime
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')

        if not api_key:
            logger.error("Alpha Vantage API key not found.")
            return

        for ticker in tickers:
            logger.info(f"Fetching data for {ticker} from Alpha Vantage")

            # Make API call to Alpha Vantage for stock data
            url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={ticker}&outputsize=full&apikey={api_key}'
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()

                # Extract time series data
                time_series = data.get('Time Series (Daily)', {})
                if time_series:
                    df = pd.DataFrame(time_series).T  # Transpose the data so dates are the index
                    df.index = pd.to_datetime(df.index)  # Convert index to datetime
                    df = df[(df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))]  # Filter by date range

                    # Rename '5. adjusted close' to 'Close' if it exists
                    if '5. adjusted close' in df.columns:
                        df = df.rename(columns={'5. adjusted close': 'Close'})
                    elif '4. close' in df.columns:
                        df = df.rename(columns={'4. close': 'Close'})
                    else:
                        logger.error(f"No 'Close' data available for ticker {ticker}.")
                        continue

                    # Calculate daily returns
                    df['Returns'] = df['Close'].pct_change().fillna(0)

                    # Calculate cumulative returns
                    df['Cumulative_Returns'] = (1 + df['Returns']).cumprod() - 1

                    # Classify the market based on the latest cumulative return
                    latest_cumulative_return = df['Cumulative_Returns'].iloc[-1]
                    current_market_condition = classify_market(latest_cumulative_return)

                    # Update or create the market condition in the database
                    MarketCondition.objects.update_or_create(ticker=ticker, defaults={'condition': current_market_condition})
                    logger.info(f"Updated market condition for {ticker}: {current_market_condition}")
                else:
                    logger.error(f"No data returned for ticker {ticker}.")
            else:
                logger.error(f"Error fetching data for {ticker} from Alpha Vantage: {response.text}")
    except Exception as e:
        logger.error(f"Error updating market conditions: {e}")


def extract_company_name(user_input):
    try:
        if not user_input:
            logger.warning("Input text is empty.")
            return None

        messages = [
            {
                "role": "system", 
                "content": "Extract only the company name or ticker symbol from the text. Do not include any additional text or descriptions."
            },
            {"role": "user", "content": user_input}
        ]

        response = client.chat.completions.create(model="chatgpt-4o-latest",
        messages=messages)

        if response.choices:
            message_content = response.choices[0].message.content.strip()
            logger.info(f"Extracted company name or ticker symbol: {message_content}")

            # Ensure we return only the name or ticker, not a descriptive string
            extracted_company_name = message_content.split(':')[-1].strip() if ':' in message_content else message_content.strip()

            if extracted_company_name.lower() != "stock_price":
                return extracted_company_name
            else:
                return None
        else:
            logger.warning("No company name or ticker symbol found.")
            return None

    except Exception as e:
        logger.error(f"Failed to extract company name: {e}")
        return None


def get_ticker_symbol_from_name(company_name):
    try:
        if not company_name:
            logger.warning("Company name is empty.")
            return []

        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            logger.error("Alpha Vantage API key not found.")
            return []

        # Use Alpha Vantage's SYMBOL_SEARCH function
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={company_name}&apikey={api_key}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            matches = [(result.get('2. name', ''), result.get('1. symbol', '')) for result in data.get('bestMatches', [])]
            logger.info(f"Ticker symbols for {company_name}: {matches}")
            return matches
        else:
            logger.error(f"Error fetching ticker symbol for company name {company_name}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error in get_ticker_symbol_from_name function: {e}")
        return []


def search_company_or_ticker(query):
    try:
        # Ensure the extracted query is valid and clean
        extracted_query = extract_company_name(query)
        if not extracted_query:
            return []

        # Use Alpha Vantage's SYMBOL_SEARCH function
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            logger.error("Alpha Vantage API key not found.")
            return []

        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={extracted_query}&apikey={api_key}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Filter the results based on whether the company name or ticker symbol contains the query (case-insensitive)
            possible_matches = [
                (result['2. name'], result['1. symbol'])
                for result in data.get('bestMatches', [])
                if extracted_query.lower() in result['2. name'].lower() or extracted_query.lower() in result['1. symbol'].lower()
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