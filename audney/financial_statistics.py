import os
import re
import requests
import logging
import us

# Get a logger instance
logger = logging.getLogger(__name__)

# Access the API key from the environment
census_api_key = os.getenv('CENSUS_API_KEY')

# Ensure the API key is available
if not census_api_key:
    logger.error("CENSUS_API_KEY is not set in the environment.")

# Budget allocation guidelines
BUDGET_GUIDELINES = {
    'housing': 0.30,  # 30% of income for housing
    'groceries': 0.10,  # 10% for groceries
    'transportation': 0.10,  # 10% for transportation
    'utilities': 0.07,  # 7% for utilities
    'clothing': 0.05,  # 5% for clothing
    'debt_repayment': 0.10  # 10% for debt repayment (this is a variable figure)
}

# Function to dynamically get FIPS code for a given state name or abbreviation
def get_state_fips(state_name_or_abbr):
    # Use the `us` library to handle state names and abbreviations
    state_info = us.states.lookup(state_name_or_abbr)
    
    if not state_info:
        logger.error(f"State name or abbreviation '{state_name_or_abbr}' not recognized.")
        return None  # Return None if the state name or abbreviation is not found

    state_fips = state_info.fips  # Get the FIPS code from the `us` package
    logger.debug(f"Using state FIPS code: {state_fips} for {state_name_or_abbr}")
    
    return state_fips

# Function to get median household income for a metropolitan area or place
def get_census_data_msa_or_place(city, state_name_or_abbr):
    # Get the FIPS code for the state
    state_fips = get_state_fips(state_name_or_abbr)
    
    if not state_fips:
        logger.error(f"State FIPS code not found for {state_name_or_abbr}")
        return None  # Return None to indicate failure to retrieve data

    # Try querying for a Metropolitan Statistical Area (MSA) first
    base_url_msa = f"https://api.census.gov/data/2019/acs/acs5"
    params_msa = {
        'get': 'NAME,B19013_001E',  # Request for name and median household income
        'for': 'metropolitan statistical area/micropolitan statistical area:*',
        'key': census_api_key
    }
    
    response_msa = requests.get(base_url_msa, params=params_msa)
    logger.debug(f"Census API MSA Response: {response_msa.text}")
    
    # If MSA data is found for the city
    if response_msa.status_code == 200:
        try:
            data_msa = response_msa.json()
            for record in data_msa[1:]:
                if city.lower() in record[0].lower():
                    try:
                        median_income = int(record[1])
                        return median_income
                    except ValueError as e:
                        logger.error(f"Error parsing income for {city}, {state_name_or_abbr}: {e}")
                        return None
        except ValueError as e:
            logger.error(f"Error parsing JSON from Census MSA API response: {e}")
    
    # Fallback to place-level data if no MSA match is found
    base_url_place = f"https://api.census.gov/data/2019/acs/acs5"
    params_place = {
        'get': 'NAME,B19013_001E',  # Request for name and median household income
        'for': 'place:*',
        'in': f'state:{state_fips}',
        'key': census_api_key
    }
    
    response_place = requests.get(base_url_place, params=params_place)
    logger.debug(f"Census API Place Response: {response_place.text}")

    if response_place.status_code == 200:
        try:
            data_place = response_place.json()
            for record in data_place[1:]:
                if city.lower() in record[0].lower():
                    try:
                        median_income = int(record[1])
                        return median_income
                    except ValueError as e:
                        logger.error(f"Error parsing income for {city}, {state_name_or_abbr}: {e}")
                        return None
        except ValueError as e:
            logger.error(f"Error parsing JSON from Census Place API response: {e}")
    
    logger.error(f"No income data found for {city}, {state_name_or_abbr}")
    return None

# Function to estimate household expenses based on income
def estimate_expenses(median_income):
    if not median_income:
        logger.warning("No income data available for expense estimation.")
        return "Income data not available."

    # Calculate expenses based on budget guidelines
    expenses = {}
    for category, percentage in BUDGET_GUIDELINES.items():
        expenses[category] = round(median_income * percentage, 2)  # Calculate the dollar amount for each category

    logger.debug(f"Estimated expenses: {expenses}")
    return expenses

# Define the extract_location function
def extract_location(user_input):
    """
    Extracts city and state from user input.

    Args:
        user_input (str): The user's query.

    Returns:
        tuple: (city, state_abbreviation) if found, otherwise (None, None).
    """
    # Pattern to capture words for city names (allowing multi-word cities) followed by a comma and a state abbreviation
    city_state_pattern = re.compile(r'([A-Za-z\s]+),\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)')

    # Search for a city-state match in the user input
    match = city_state_pattern.search(user_input)

    if match:
        city = match.group(1).strip()  # Get the city name
        state_abbr = match.group(2).upper()  # Get the state abbreviation
        logger.debug(f"Extracted Location: City = {city}, State = {state_abbr}")
        return city, state_abbr
    
    logger.warning("No city or state found in user input.")
    return None, None  # Return None if no match is found