import os
import logging
from openai import OpenAI

client = OpenAI()
from openai import OpenAI
from .market_analysis import get_stock_price, extract_company_name, calculate_user_age, search_company_or_ticker
from .financial_statistics import get_census_data_msa_or_place, estimate_expenses
from scipy.spatial.distance import cosine


logger = logging.getLogger(__name__)

def get_embedding(text):
    response = client.embeddings.create(model="text-embedding-ada-002",  # Ensure this is available in your OpenAI account
    input=text)
    return response.data[0].embedding

def classify_using_embeddings(user_input):
    stock_query_intent = "Ask about stock price"

    # Get the embeddings for the user input and the stock price intent
    input_embedding = get_embedding(user_input)
    stock_intent_embedding = get_embedding(stock_query_intent)

    # Compare their similarity using cosine distance
    similarity_score = 1 - cosine(input_embedding, stock_intent_embedding)  # Cosine similarity

    # Classify based on a threshold
    if similarity_score > 0.8:  # Adjust threshold as needed
        return "stock_price"
    else:
        return "other"
def classify_query_with_gpt(user_input):
    try:
        # Ensure the API key is available in the environment
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found in the environment.")
            return "other"

        client = OpenAI(api_key=api_key)

        # Construct messages to instruct the GPT model
        messages = [
            {
                "role": "system",
                "content": """
                You are a financial assistant. Your job is to classify user queries into one of the following categories: 
                - 'stock_price': If the user asks for a stock's price, value, or performance. 
                  Examples include: "What is the price of Tesla stock?", "How much is Microsoft stock worth?", "Give me the current value of AAPL."
                - 'financial_advice': If the user asks for financial guidance or advice. 
                  Examples include: "How should I budget my income?", "How can I save for retirement?"
                - 'investment_strategy': If the user asks for strategies to invest. 
                  Examples include: "What are good strategies for investing in real estate?", "Should I diversify my portfolio?"
                - 'other': For any unrelated queries. 
                  Examples include: "What is the weather today?"
                Classify the user's query accurately based on these categories.
                """
            },
            {"role": "user", "content": user_input}
        ]

        # Call OpenAI's GPT model for classification
        response = client.chat.completions.create(model="chatgpt-4o-latest", messages=messages)

        # Log the raw response for debugging purposes
        logger.debug(f"OpenAI classification response: {response}")

        # Extract the classification result from the response
        query_type = response.choices[0].message.content.strip().lower() if response.choices else "other"

        # Strip out "Category: " or similar prefix from the response
        query_type = query_type.replace("category: ", "").strip()

        logger.info(f"Query type classified as: '{query_type}' for input: {user_input}")

        # Ensure proper mapping of query types to valid categories
        classification_mapping = {
            'stock price': 'stock_price',
            'stock_price': 'stock_price',
            'stock': 'stock_price',
            'financial advice': 'financial_advice',
            'financial_advice': 'financial_advice',
            'advice': 'financial_advice',
            'investment strategy': 'investment_strategy',
            'investment_strategy': 'investment_strategy',
            'strategy': 'investment_strategy'
        }

        # Normalize misclassifications
        query_type = classification_mapping.get(query_type, query_type)

        # Handle cases where the classification might miss stock-related keywords
        if query_type == "other":
            stock_related_words = ["stock", "shares", "price of", "value of", "worth", "going for"]
            for word in stock_related_words:
                if word in user_input.lower():
                    query_type = "stock_price"
                    break

        return query_type

    except Exception as e:
        # Log the error and return 'other' as the default classification
        logger.error(f"Error classifying query: {e}")
        return "other"

# Handler for stock price queries
def handle_stock_price_query(user_input):
    logger.debug(f"Entered handle_stock_price_query with user_input: {user_input}")

    company_name_or_symbol = extract_company_name(user_input)
    logger.debug(f"Extracted company name or symbol: {company_name_or_symbol}")

    if not company_name_or_symbol:
        response_message = "Sorry, I couldn't extract any valid company name or ticker symbol from your query."
        logger.warning("No valid company name or symbol found in user input.")
        return response_message, False

    possible_matches = search_company_or_ticker(company_name_or_symbol)
    logger.debug(f"Possible matches found for company_name_or_symbol '{company_name_or_symbol}': {possible_matches}")

    if isinstance(possible_matches, tuple):
        # Single match found
        company_name, ticker_symbol = possible_matches
        logger.debug(f"Single match: company_name={company_name}, ticker_symbol={ticker_symbol}")
        stock_price = get_stock_price(ticker_symbol)
        logger.debug(f"Stock price for {ticker_symbol}: {stock_price}")
        response_message = f"Currently, {company_name} ({ticker_symbol}) is priced at {stock_price}."
        contains_html = False
    elif len(possible_matches) > 1:
        # Multiple matches found
        logger.debug(f"Multiple matches found: {possible_matches}")
        response_message = "I found multiple companies with that name, please choose the one you're referring to: "
        response_message += "<ul>"
        for name, ticker in possible_matches:
            response_message += f"<li><a href='#' onclick='fetchStockPrice(\"{ticker}\", \"{name}\")'>{name} ({ticker})</a></li>"
        response_message += "</ul>"
        contains_html = True
    else:
        # No matches found
        logger.debug(f"No matches found for company_name_or_symbol: {company_name_or_symbol}")
        response_message = "Sorry, I couldn't find the stock price for the company you mentioned."
        contains_html = False

    logger.info(f"Final response message: {response_message}, Contains HTML: {contains_html}")
    return response_message, contains_html

# Handler for financial advice queries
def handle_financial_advice(user_input, user):
    user_profile = user.userprofile
    user_age = calculate_user_age(user_profile.date_of_birth)  # Assuming this exists
    user_financial_goal = user_profile.financial_goals
    city, state = user_profile.city, user_profile.state

    # Use census and expense data
    median_income = get_census_data_msa_or_place(city, state, os.getenv('CENSUS_API_KEY'))

    if isinstance(median_income, int):
        expense_estimates = estimate_expenses(median_income)
        expenses_str = ", ".join([f"{category}: ${amount}" for category, amount in expense_estimates.items()])
    else:
        expenses_str = "Income and expense data not available."

    user_context = f"I am {user_age} years old. My financial goal is {user_financial_goal}. " \
                   f"Estimated household expenses: {expenses_str}."

    return user_context

# Handler for investment strategy
def handle_investment_strategy(user_input, user):
    user_profile = user.userprofile
    risk_tolerance = user_profile.get_risk_tolerance_display()

    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        messages = [
            {"role": "system", "content": f"Provide investment strategy advice for a user with this risk tolerance: {risk_tolerance}."},
            {"role": "user", "content": user_input}
        ]
        response = client.chat.completions.create(model="chatgpt-4o-latest", messages=messages)
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating investment strategy advice: {e}")
        return "An error occurred while processing your investment strategy request."

# Add more handlers as needed...