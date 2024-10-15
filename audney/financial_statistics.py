import os
import re
import requests
import logging
import us
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Get a logger instance
logger = logging.getLogger(__name__)

# Access the OpenAI API key from the environment
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    logger.error("OPENAI_API_KEY is not set in the environment.")

# Set up OpenAI with the API key

# Access the API key from the environment
census_api_key = os.getenv('CENSUS_API_KEY')

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
    state_info = us.states.lookup(state_name_or_abbr)

    if not state_info:
        logger.error(f"State name or abbreviation '{state_name_or_abbr}' not recognized.")
        return None

    state_fips = state_info.fips
    logger.debug(f"Using state FIPS code: {state_fips} for {state_name_or_abbr}")

    return state_fips

# Function to get median household income for a metropolitan area or place
def get_census_data_msa_or_place(city, state_name_or_abbr):
    state_fips = get_state_fips(state_name_or_abbr)

    if not state_fips:
        logger.error(f"State FIPS code not found for {state_name_or_abbr}")
        return None

    # Try querying for a Metropolitan Statistical Area (MSA) first
    base_url_msa = f"https://api.census.gov/data/2019/acs/acs5"
    params_msa = {
        'get': 'NAME,B19013_001E',
        'for': 'metropolitan statistical area/micropolitan statistical area:*',
        'key': census_api_key
    }

    response_msa = requests.get(base_url_msa, params=params_msa)
    logger.debug(f"Census API MSA Response: {response_msa.text}")

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
        'get': 'NAME,B19013_001E',
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

    expenses = {category: round(median_income * percentage, 2) for category, percentage in BUDGET_GUIDELINES.items()}
    logger.debug(f"Estimated expenses: {expenses}")
    return expenses

def extract_location(user_input, user_profile):
    """
    Extracts the city and state from the user's input using ChatGPT 4.0.
    If no city and state are found in the input, pull from the user profile.
    """

    # Define the system prompt to ensure ChatGPT extracts the city and state
    system_prompt = """
    You are an assistant. Extract the city and state from the user's input. If no city or state is mentioned, return None. 
    If there is only one location (city or state), provide that. Do not return additional details other than city and state.
    """

    # Call the OpenAI API with user input and system instructions
    try:
        response = client.chat.completions.create(model="chatgpt-4o-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ])
        # Extract the city and state from the response
        chatgpt_response = response.choices[0].message.content.strip()
        logger.info(f"ChatGPT-4 extracted location: {chatgpt_response}")

        # If OpenAI doesn't provide a location, check the user's profile
        if not chatgpt_response:
            city = user_profile.get('city')
            state = user_profile.get('state')
            if city and state:
                logger.info(f"Using location from user profile: {city}, {state}")
                return city, state
            else:
                logger.warning("No location provided in input or user profile.")
                return None, None

        # Assuming ChatGPT returns the location in a "City, State" format
        city, state = chatgpt_response.split(", ")
        return city.strip(), state.strip().upper()

    except Exception as e:
        logger.error(f"Error while querying OpenAI: {e}")
        return None, None

# Function to get demographic data for a city
def get_demographic_data(city, state_name_or_abbr):
    state_fips = get_state_fips(state_name_or_abbr)
    if not state_fips:
        return None

    base_url = "https://api.census.gov/data/2019/acs/acs5/profile"
    params = {
        'get': 'NAME,DP05_0001E,B17001_002E',
        'for': 'place:*',
        'in': f'state:{state_fips}',
        'key': census_api_key
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            for record in data[1:]:
                if city.lower() in record[0].lower():
                    total_population = int(record[1])
                    individuals_below_poverty = int(record[2])
                    poverty_rate = (individuals_below_poverty / total_population) * 100 if total_population else 0
                    return {'total_population': total_population, 'poverty_rate': poverty_rate}
        except ValueError as e:
            logger.error(f"Error parsing demographic data: {e}")
    else:
        logger.error(f"Failed to retrieve demographic data: {response.text}")
    return None

# Function to get employment data for a city
def get_employment_data(city, state_name_or_abbr):
    state_fips = get_state_fips(state_name_or_abbr)
    if not state_fips:
        logger.error(f"State FIPS code not found for '{state_name_or_abbr}'")
        return None

    base_url = "https://api.census.gov/data/2019/acs/acs5"
    params = {
        'get': 'NAME,B23025_003E,B23025_004E,B23025_005E',
        'for': 'place:*',
        'in': f'state:{state_fips}',
        'key': census_api_key
    }

    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        try:
            data = response.json()
            logger.debug(f"Employment data retrieved: {data}")

            city_input = city.strip().lower()

            for record in data[1:]:
                place_full_name = record[0].split(',')[0].strip().lower()

                descriptors = [' city', ' town', ' village', ' cdp']
                place_name = place_full_name
                for desc in descriptors:
                    if place_full_name.endswith(desc):
                        place_name = place_full_name[:-len(desc)]
                        break

                if place_name == city_input:
                    labor_force = int(record[1]) if record[1] not in ('null', None, '') else None
                    employed = int(record[2]) if record[2] not in ('null', None, '') else None
                    unemployed = int(record[3]) if record[3] not in ('null', None, '') else None

                    if labor_force and employed is not None:
                        employment_rate = (employed / labor_force) * 100
                    else:
                        employment_rate = None

                    if labor_force and unemployed is not None:
                        unemployment_rate = (unemployed / labor_force) * 100
                    else:
                        unemployment_rate = None

                    logger.debug(f"Employment data for {city}: Labor Force: {labor_force}, Employed: {employed}, Unemployment Rate: {unemployment_rate}")
                    return {
                        'labor_force': labor_force,
                        'employed': employed,
                        'unemployed': unemployed,
                        'employment_rate': employment_rate,
                        'unemployment_rate': unemployment_rate
                    }
            logger.warning(f"No employment data found for '{city}', '{state_name_or_abbr}'")
        except ValueError as e:
            logger.error(f"Error parsing employment data: {e}")
    else:
        logger.error(f"Failed to retrieve employment data: {response.text}")
    return None

# Function to get housing data for a city
def get_housing_data(city, state_name_or_abbr):
    state_fips = get_state_fips(state_name_or_abbr)
    if not state_fips:
        return None

    base_url = "https://api.census.gov/data/2019/acs/acs5"
    params = {
        'get': 'NAME,B25077_001E,B25064_001E',
        'for': 'place:*',
        'in': f'state:{state_fips}',
        'key': census_api_key
    }

    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        try:
            data = response.json()
            for record in data[1:]:
                if city.lower() in record[0].lower():
                    median_home_value = int(record[1]) if record[1] not in ('null', None, '') else None
                    median_gross_rent = int(record[2]) if record[2] not in ('null', None, '') else None
                    return {
                        'median_home_value': median_home_value,
                        'median_gross_rent': median_gross_rent
                    }
        except ValueError as e:
            logger.error(f"Error parsing housing data: {e}")
    else:
        logger.error(f"Failed to retrieve housing data: {response.text}")
    return None