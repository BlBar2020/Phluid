# Import necessary modules and functions
import os
from datetime import datetime
from django.utils import timezone
from django.utils.timezone import make_aware, now, timedelta
import logging
import time
from django.http import JsonResponse, HttpResponseServerError

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import auth, messages
from django.contrib.auth import update_session_auth_hash, authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.utils.html import escape
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import auth
from django.db.models import Value, CharField, TextField
# from django_otp.oath import TOTP
from django.utils.dateformat import format
from django.views.decorators.http import require_http_methods, require_GET
import json
from django.utils.timezone import now

# Import local modules and functions
from .models import UserMessage, AudneyMessage, StockPriceResponse, MarketCondition, UserProfile
from audney.models import UserProfile
from .forms import UserProfileForm, UserForm
from .market_analysis import get_stock_price, calculate_user_age, update_market_conditions, extract_company_name, get_ticker_symbol_from_name
from django.core.mail import EmailMessage
from .forms import SupportForm
import pandas as pd
import requests

# Import OpenAI module
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
from .financial_statistics import get_census_data_msa_or_place, estimate_expenses, extract_location, get_demographic_data, get_employment_data, get_housing_data
from .query_handlers import classify_query_with_gpt, handle_stock_price_query

# Set the OpenAI API key

# Get a logger instance
logger = logging.getLogger(__name__)

# Fetch Market News
def get_market_news():
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={os.getenv('ALPHA_VANTAGE_API_KEY')}"
    response = requests.get(url)
    if response.status_code == 200:
        news_data = response.json()
        if 'feed' in news_data:
            return pd.DataFrame(news_data['feed'])  # Convert news feed to a Pandas DataFrame
        else:
            print("No market news found.")
            return None
    else:
        print(f"Error fetching news: {response.status_code}")
        return None
# Analyze Market News
def analyze_market_news(news_df):
    # Example: Filter by relevance score or sentiment, using top 5
    return news_df.head(5) if 'summary' in news_df.columns else None

def ask_openai(user_input, user):
    logger.debug(f"Entered ask_openai with user_input: {user_input}, user: {user}")

    # First, classify the user's query using GPT
    query_type = classify_query_with_gpt(user_input).strip().lower()
    logger.info(f"Query type classified as: {query_type} for input: {user_input}")

    # Check for stock price query and handle appropriately
    if query_type == "stock_price":
        logger.info("Handling stock price query...")
        stock_price_response, contains_html = handle_stock_price_query(user_input)
        logger.debug(f"Stock price response from handle_stock_price_query: {stock_price_response}, contains_html: {contains_html}")

        if stock_price_response:
            logger.info(f"Returning valid stock price response: {stock_price_response}, skipping financial advice.")
            return stock_price_response
        else:
            logger.error("Stock price response is empty or invalid. Proceeding to default error handling for stock prices.")
            return "Sorry, I couldn't fetch the stock price at this time."
    else:
        logger.info(f"Query type '{query_type}' is not 'stock_price', proceeding with financial advice flow.")

    try:
        # Fetch and update market conditions
        update_market_conditions()
        market_conditions = MarketCondition.objects.all()
        market_conditions_str = '\n'.join([f"Currently, '{mc.ticker}' seems to be in a {mc.condition} market." for mc in market_conditions])
        logger.debug(f"Market conditions: {market_conditions_str}")

        # Gather user financial profile details
        user_profile = user.userprofile
        user_age = calculate_user_age(user_profile.date_of_birth)
        user_financial_goal = user_profile.financial_goals
        city = user_profile.city
        state = user_profile.state
        additional_user_details = f"Risk Tolerance: {user_profile.get_risk_tolerance_display()}, " \
                                  f"Income Level: {user_profile.get_income_level_display()}, " \
                                  f"Dependents: {user_profile.get_has_dependents_display()}, " \
                                  f"Savings Coverage: {user_profile.get_savings_months_display()}."
        logger.debug(f"User profile: age={user_age}, goals={user_financial_goal}, city={city}, state={state}, additional_details={additional_user_details}")

        # Extract city/state if specified in the user's query or fall back to profile
        logger.debug(f"User input: {user_input}")
        specified_city, specified_state = extract_location(user_input, {"city": city, "state": state})
        logger.debug(f"Extracted location from input: city={specified_city}, state={specified_state}")

        # If the user specifies a different location, use it; otherwise, use profile location
        if specified_city and specified_state:
            city, state = specified_city, specified_state
            location_context = f"Based on data for {city}, {state}:"
        else:
            location_context = f"Based on data for your location ({city}, {state}):"
        logger.debug(f"Location context: {location_context}")

        # Get census data for user's city and state or the specified location
        median_income = get_census_data_msa_or_place(city, state)
        logger.debug(f"Median income for {city}, {state}: {median_income}")

        # Get additional demographic, employment, and housing data
        demographic_data = get_demographic_data(city, state)
        logger.debug(f"Demographic data for {city}, {state}: {demographic_data}")

        employment_data = get_employment_data(city, state)
        logger.debug(f"Employment data for {city}, {state}: {employment_data}")

        housing_data = get_housing_data(city, state)
        logger.debug(f"Housing data for {city}, {state}: {housing_data}")

        # Construct location message with the retrieved data
        location_messages = []

        if isinstance(median_income, int):
            location_messages.append(f"The median household income in {city}, {state} is ${median_income}.")
            expense_estimates = estimate_expenses(median_income)
            expenses_str = ", ".join([f"{category}: ${amount}" for category, amount in expense_estimates.items()])
            location_messages.append(f"Estimated expenses based on median income are: {expenses_str}.")
        else:
            location_messages.append("Income data not available for the specified location.")

        if demographic_data:
            total_population = demographic_data.get('total_population')
            poverty_rate = demographic_data.get('poverty_rate')
            if total_population is not None and poverty_rate is not None:
                location_messages.append(f"The total population is {total_population}, with a poverty rate of {poverty_rate:.2f}%.")
            else:
                location_messages.append("Demographic data is incomplete.")
        else:
            location_messages.append("Demographic data not available.")

        if employment_data:
            employment_rate = employment_data.get('employment_rate')
            unemployment_rate = employment_data.get('unemployment_rate')
            if employment_rate is not None and unemployment_rate is not None:
                location_messages.append(f"The employment rate is {employment_rate:.2f}%, and the unemployment rate is {unemployment_rate:.2f}%.")
            else:
                location_messages.append("Employment data is incomplete.")
        else:
            location_messages.append("Employment data not available.")

        if housing_data:
            median_home_value = housing_data.get('median_home_value')
            median_gross_rent = housing_data.get('median_gross_rent')
            if median_home_value is not None:
                location_messages.append(f"The median home value in {city}, {state} is ${median_home_value}.")
            else:
                location_messages.append("Median home value data not available.")
            if median_gross_rent is not None:
                location_messages.append(f"The median gross rent in {city}, {state} is ${median_gross_rent}.")
            else:
                location_messages.append("Median gross rent data not available.")
        else:
            location_messages.append("Housing data not available.")

        # Combine all location messages
        location_message = " ".join(location_messages)
        logger.debug(f"Location message: {location_message}")

        # Construct user financial context as system knowledge
        user_context = f"The user is {user_age} years old, with financial goals set as: {user_financial_goal}. {additional_user_details}"
        logger.debug(f"User context: {user_context}")

        # Fetch and summarize market news
        news_df = get_market_news()
        if news_df is not None:
            analyzed_news = analyze_market_news(news_df)
            if analyzed_news is not None:
                news_summary = "\n".join(analyzed_news['summary'].tolist())
            else:
                news_summary = "No relevant market news available."
        else:
            news_summary = "No market news could be fetched."
        logger.debug(f"Market news summary: {news_summary}")

        # Adjusted System Message
        system_message = (
            f"You are a professional, emotionally intelligent, and friendly financial advisor named Audney. "
            f"Your goal is to educate the user on their finances and provide tailored advice.\n\n"
            f"{user_context}\n\n"
            f"{location_context}\n\n"
            f"{location_message}\n\n"
            f"Here is some market data:\n{market_conditions_str}\n\n"
            f"Additionally, here are the latest market news updates:\n{news_summary}\n\n"
            "**Instructions:** Use the above data to provide a detailed and specific response to the user's query. "
            "Focus on the data provided and avoid mentioning any limitations of your knowledge or access to real-time data. "
            "Do not include disclaimers about data availability. Present the information confidently and helpfully.\n\n"
            "When responding, consider the user's financial goals, experience level, risk tolerance, income level, "
            "dependents, and market data to provide personalized advice. Your tone should be friendly, supportive, and informative, "
            "like a personal financial advisor who is also a friend. Use markdown formatting when appropriate to enhance readability, especially for lists and headings."
        )
        logger.debug(f"System message for GPT: {system_message}")

        # Incorporate conversation history (Optional: You can include this if needed)
        recent_user_messages = UserMessage.objects.filter(user=user).order_by('-created_at')[:10]
        recent_audney_messages = AudneyMessage.objects.filter(user=user).order_by('-created_at')[:10]

        # Combine and sort messages by timestamp
        combined_messages = list(recent_user_messages) + list(recent_audney_messages)
        combined_messages.sort(key=lambda msg: msg.created_at)

        # Build the messages list for the API call
        messages = [
            {"role": "system", "content": system_message},
        ]

        # Optionally include conversation history
        for msg in combined_messages:
            if isinstance(msg, UserMessage):
                messages.append({"role": "user", "content": msg.message})
            elif isinstance(msg, AudneyMessage):
                messages.append({"role": "assistant", "content": msg.message})

        # Add the current user input
        messages.append({"role": "user", "content": user_input})

        logger.debug(f"Messages sent to OpenAI: {messages}")

        chat_completion = client.chat.completions.create(model="chatgpt-4o-latest",
        messages=messages)

        # Handle the API response
        if chat_completion.choices:
            answer = chat_completion.choices[0].message.content.strip()
            logger.info(f"Received response from OpenAI: {answer}")
            return answer
        else:
            logger.error("No response from OpenAI.")
            return "No response from OpenAI."

    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        return "An error occurred while processing your request."

@require_http_methods(["GET", "POST"])
def chatbot_response(request):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'You must be logged in to chat.', 'html': False, 'timestamp': ""})

    user_input = ''
    response_message = ""
    contains_html = False

    if request.method == 'POST':
        data = json.loads(request.body)
        user_input = data.get('message', '').strip()
        UserMessage.objects.create(
            user=request.user,
            message=user_input,
            message_type='user',
            created_at=make_aware(datetime.now())
        )
    else:  # GET request
        user_input = request.GET.get('message', '').strip()
        UserMessage.objects.create(
            user=request.user,
            message=user_input,
            message_type='user',
            created_at=make_aware(datetime.now())
        )

    # Use OpenAI to classify the query
    query_type = classify_query_with_gpt(user_input).strip().lower().strip("'\" ")  # Strip surrounding quotes
    logger.info(f"Query type classified as: '{query_type}' for input: {user_input}")

    # Ensure debugging logs to capture the exact type and comparison
    logger.debug(f"Raw query_type: {repr(query_type)} (before comparison)")

    # Handle stock price queries
    if query_type == "stock_price":
        logger.debug(f"query_type is 'stock_price' (confirmed match), proceeding with stock price handling.")
        company_name_or_symbol = extract_company_name(user_input)

        if not company_name_or_symbol:
            return JsonResponse({"message": "Sorry, I couldn't determine the company or stock you're referring to."})

        possible_matches = get_ticker_symbol_from_name(company_name_or_symbol)

        if len(possible_matches) == 1:
            # Fetch the stock price for the single match
            company_name, ticker_symbol = possible_matches[0]
            stock_price = get_stock_price(ticker_symbol)
            ticker_quote = f"Currently, {company_name} ({ticker_symbol}) is priced at {stock_price}."
            contains_html = False

            # Delay to prevent race condition
            time.sleep(1)

            # Prevent duplicate responses within a short time frame
            recent_time_threshold = timezone.now() - timedelta(seconds=5)
            existing_response = StockPriceResponse.objects.filter(
                user=request.user,
                query=user_input,
                ticker_quote=ticker_quote,
                created_at__gte=recent_time_threshold
            ).exists()

            if not existing_response:
                StockPriceResponse.objects.create(
                    user=request.user,
                    query=user_input,
                    ticker_quote=ticker_quote,
                    message_type='system',
                    created_at=make_aware(datetime.now())
                )
            else:
                logger.info("Duplicate stock response detected, not saving.")

            response_message = ticker_quote

            # Store the assistant's response
            AudneyMessage.objects.create(
                user=request.user,
                user_query=user_input,
                message=response_message,
                contains_html=contains_html,
                message_type='audney',
                created_at=make_aware(datetime.now())
            )

        elif len(possible_matches) > 1:
            # If there are multiple matches, return them to the user for selection
            response_message = "I found multiple companies with that name, please choose the one you're referring to: "
            response_message += "<ul>"
            for name, ticker in possible_matches:
                # Updated to use class and data attributes instead of onclick
                response_message += f"<li><a href='#' class='stock-link' data-ticker-symbol='{ticker}' data-company-name='{name}'>{name} ({ticker})</a></li>"
            response_message += "</ul>"
            contains_html = True

            # Store the assistant's response
            AudneyMessage.objects.create(
                user=request.user,
                user_query=user_input,
                message=response_message,
                contains_html=contains_html,
                message_type='audney',
                created_at=make_aware(datetime.now())
            )

        else:
            # Handle case where no matches are found
            response_message = "Sorry, I couldn't find the stock price for the company you mentioned."
            contains_html = False

            # Store the assistant's response
            AudneyMessage.objects.create(
                user=request.user,
                user_query=user_input,
                message=response_message,
                contains_html=contains_html,
                message_type='audney',
                created_at=make_aware(datetime.now())
            )

    else:
        # Handle other types of queries using OpenAI API
        logger.debug(f"query_type is not 'stock_price' (query_type = {repr(query_type)}), proceeding with other handling.")
        response = ask_openai(user_input, request.user)
        response_message = response if response else "Sorry, I couldn't understand your query."
        contains_html = False

        # Store the assistant's response
        AudneyMessage.objects.create(
            user=request.user,
            user_query=user_input,
            message=response_message,
            contains_html=contains_html,
            message_type='audney',
            created_at=make_aware(datetime.now())
        )

    # Format the timestamp for the response
    timestamp_format = make_aware(datetime.now()).strftime('%Y-%m-%d %H:%M:%S')

    return JsonResponse({
        'message': response_message,
        'html': contains_html,
        'timestamp': timestamp_format,
    })

@require_GET
def get_stock_price_view(request):
    user = request.user
    symbol = request.GET.get('symbol')
    company_name_input = request.GET.get('companyName')

    if user.is_authenticated and symbol:
        try:
            # Extract and clean company name
            company_name = extract_company_name(company_name_input) if company_name_input else "Unknown company"
            escaped_company_name = escape(company_name)

            price = get_stock_price(symbol)

            # Log and store the stock price response
            StockPriceResponse.objects.create(
                user=user,
                query=f"Stock price check for {escaped_company_name} ({symbol})",
                ticker_quote=f"{escaped_company_name} is currently priced at {price}",
                message_type='system'
            )

            return JsonResponse({'success': True, 'price': price, 'companyName': escaped_company_name})
        except Exception as e:
            logger.error(f"Error fetching stock price for {symbol}: {e}")
            return JsonResponse({'success': False, 'error': f"An error occurred: {str(e)}"})
    else:
        error_message = 'No symbol provided or user not authenticated.'
        logger.warning(error_message)
        return JsonResponse({'success': False, 'error': error_message})

@login_required
def audney(request):
    if request.method == 'POST':
        # Process the POST request with user's message
        data = json.loads(request.body) if request.body else request.POST
        user_input = data.get('message', '').strip()

        # Save user's input as a UserMessage
        UserMessage.objects.create(
            user=request.user,
            message=user_input,
            message_type='user',  # Ensure you have defined 'user' in MESSAGE_TYPES
            created_at=now()
        )

        # Ask OpenAI for a response
        response, contains_html = ask_openai(user_input, request.user)

        if response:
            logger.debug(f"contains_html value: {contains_html}")
            # Determine the type of response and choose the appropriate model
            recent_time_threshold = now() - timedelta(seconds=5)  # Adjust the timedelta as needed
            existing_message = AudneyMessage.objects.filter(
                user=request.user,
                message=response,
                created_at__gte=recent_time_threshold
            ).exists()

            if not existing_message:
                AudneyMessage.objects.create(
                    user=request.user,
                    user_query=user_input,
                    message=response,
                    contains_html=contains_html,
                    message_type='audney',
                )
            else:
                logger.info("Duplicate message detected, not saving.")
            return JsonResponse({'message': response, 'html': contains_html})
        else:
            logger.error('No response received from OpenAI.')
            return JsonResponse({'error': 'Sorry, there was an error processing your request.'}, status=500)

    # If the method is not POST, gather and sort all related messages
    else:
        user_messages = UserMessage.objects.filter(user=request.user).order_by('created_at')
        audney_messages = AudneyMessage.objects.filter(user=request.user).order_by('created_at')
        stock_responses = StockPriceResponse.objects.filter(user=request.user).order_by('created_at')

        # Combine querysets
        all_messages = list(user_messages) + list(audney_messages) + list(stock_responses)
        # Sort all messages by created_at
        all_messages.sort(key=lambda x: x.created_at)

        return render(request, 'chatbot.html', {
            'all_messages': all_messages,
            # If you need to distinguish between message types in the template, consider passing them separately or adding a type attribute
        })

@login_required
def get_chat_history(request):
    try:
        user = request.user

        # Use null for 'query' and 'ticker_quote' for UserMessage and AudneyMessage
        user_messages = UserMessage.objects.filter(user=user).annotate(
            type=Value('user', CharField()),
            query=Value(None, TextField()),  # Use null value
            ticker_quote=Value(None, TextField()),  # Use null value
        ).values('id', 'message', 'created_at', 'type', 'query', 'ticker_quote')

        audney_messages = AudneyMessage.objects.filter(user=user).annotate(
            type=Value('audney', CharField()),
            query=Value(None, TextField()),  # Use null value
            ticker_quote=Value(None, TextField()),  # Use null value
        ).values('id', 'message', 'created_at', 'type', 'query', 'ticker_quote')

        stock_responses = StockPriceResponse.objects.filter(user=user).annotate(
            type=Value('stock_response', CharField()),
        ).values('id', 'ticker_quote', 'created_at', 'type', 'query', 'ticker_quote')

        # Combine querysets using 'union' and order by 'created_at'
        all_messages = user_messages.union(audney_messages, stock_responses).order_by('created_at')

        # After preparing the all_messages queryset
        logger.debug(f"Combined QuerySet (all_messages) Contents: {list(all_messages)}")

        # Convert queryset to a list of dictionaries for the JsonResponse
        data = list(all_messages)

        # Format each message's timestamp and prepare for JSON response
        for msg in data:
            msg['timestamp'] = msg['created_at'].strftime('%Y-%m-%d %H:%M:%S') if msg['created_at'] is not None else "Timestamp not available"
            del msg['created_at']  # Remove 'created_at' as it's no longer needed

        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}", exc_info=True)
        return HttpResponseServerError('Internal Server Error')

def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Log the user in
            auth_login(request, user)
            # Redirect to the desired page after successful login
            return redirect('chatbot')
        else:
            # If authentication fails, show an error message
            messages.error(request, 'Invalid username or password')
            return render(request, 'login.html', {'error_message': 'Invalid username or password'})
    else:
        # If the request method is not POST, display the login page
        # Check for the 'timed_out' parameter
        if 'timed_out' in request.GET:
            messages.add_message(request, messages.INFO, 'Your session has expired. Please log in again.')

        return render(request, 'login.html')

    # This decorator ensures that only logged-in users can access this view
@login_required
def update_profile(request):
    user = request.user
    profile = UserProfile.objects.get(user=user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()

            # Update the session with the new password if changed
            if user_form.cleaned_data.get('password1'):
                update_session_auth_hash(request, user)

            messages.success(request, 'Profile updated successfully.')
            return redirect('chatbot')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        user_form = UserForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    return render(request, 'update_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })
# Define a function to handle registration requests
def register(request):
    # Check if the request method is POST
    if request.method == 'POST':
        # Create a user form and a profile form with the POST data
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        # Create a context dictionary to hold the forms
        context = {'user_form': user_form, 'profile_form': profile_form}

        # If both forms are valid
        if user_form.is_valid() and profile_form.is_valid():
            try:
                # Start a transaction
                with transaction.atomic():
                    # Save the user form
                    user = user_form.save()
                    # Get or create the user's profile
                    profile, created = UserProfile.objects.get_or_create(
                        user=user)
                    # Update the profile with the data from the profile form and save it
                    profile.date_of_birth = profile_form.cleaned_data['date_of_birth']
                    profile.financial_goals = profile_form.cleaned_data['financial_goals']
                    profile.save()
                    # Show a success message
                    messages.success(
                        request, 'Your account has been created successfully!')
                    # Redirect the user to the login view
                    return redirect('login')
            except IntegrityError as e:
                # If an IntegrityError occurs, log it and show an error message
                logger.error(
                    f"IntegrityError when creating a user profile: {e}")
                context['error_message'] = 'An error occurred while creating the account. Please try again.'
            except Exception as e:
                # If another exception occurs, log it and show an error message
                logger.error(f"Error creating account: {e}")
                context['error_message'] = 'An error occurred while creating the account: ' + \
                    str(e)
    else:
        # If the request method is not POST, create empty forms
        context = {
            'user_form': UserForm(),
            'profile_form': UserProfileForm()
        }

    # Render the register.html template with the context
    return render(request, 'register.html', context)

# Define a function to handle logout requests
def logout(request):
    # Log the user out
    auth.logout(request)
    # Redirect the user to the login view
    return redirect('login')

def support(request):
    # Initialize the form for both GET and POST requests
    form = SupportForm(user=request.user)  # Initialize with user, assuming the form handles an unbound form this way

    if request.method == 'POST':
        form = SupportForm(request.POST, user=request.user)  # Rebind form with POST data and user
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            if request.user.is_authenticated:
                sender_email = request.user.email  # Use the logged-in user's email
            else:
                sender_email = form.cleaned_data['email']  # Use the provided email for unauthenticated users
            # Send email
            email = EmailMessage(
                subject,
                message,
                'blake@phluid.ai',  # From email
                ['blake@phluid.ai'],  # To email
                headers={'Reply-To': sender_email}
            )
            email.send()
            return redirect('support_success', from_page=request.GET.get('from', 'default'))

    # Check if the 'from' query parameter is set to 'update_profile'
    is_from_update_profile = request.GET.get('from') == 'update_profile'

    # Prepare context
    context = {
        'form': form,
        'is_from_update_profile': is_from_update_profile,
    }

    return render(request, 'support.html', context)

def support_success(request, from_page='default'):
    # Determine the source from the query parameter
    context = {'source_page': from_page}
    return render(request, 'support_success.html', context)