# Import necessary modules and functions
import os
from datetime import datetime
from django.utils import timezone
from django.utils.timezone import make_aware, now, timedelta
import logging
import time
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest, HttpResponseServerError

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils.html import strip_tags

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import auth, messages
from django.contrib.auth import update_session_auth_hash, authenticate, login as auth_login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction, IntegrityError, models
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils.html import escape
from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import auth
from django.db.models import Value, CharField, TextField
# from django_otp.oath import TOTP
from django.utils.html import mark_safe
from django.utils.dateformat import format
from django.views.decorators.http import require_http_methods, require_POST, require_GET
import json
from django.utils.timezone import now
from django.db.models import F

# Import local modules and functions
from .models import UserMessage, AudneyMessage, StockPriceResponse, MarketCondition, UserProfile
from audney.models import UserProfile
from .forms import UserProfileForm, UserForm
from .market_analysis import get_stock_price, search_company_or_ticker, calculate_user_age, update_market_conditions, extract_company_name
from django.core.mail import send_mail
from django.core.mail import EmailMessage
from .forms import SupportForm
import pandas as pd
import requests

# Import OpenAI module
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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

# Call OpenAI API for personalized advice
def ask_openai(user_input, user):

    # Update market conditions
    update_market_conditions()
    market_conditions = MarketCondition.objects.all()
    market_conditions_str = '\n'.join([f"Currently, '{mc.ticker}' seems to be in a {mc.condition} market." for mc in market_conditions])

    # Gather user financial profile
    user_profile = user.userprofile
    user_age = calculate_user_age(user_profile.date_of_birth)
    user_financial_goal = user_profile.financial_goals
    additional_user_details = f"Risk Tolerance: {user_profile.get_risk_tolerance_display()}, " \
                              f"Income Level: {user_profile.get_income_level_display()}, " \
                              f"Dependents: {user_profile.get_has_dependents_display()}, " \
                              f"Savings Coverage: {user_profile.get_savings_months_display()}."
    user_context = f"I am {user_age} years old. My financial goal is {user_financial_goal}. {additional_user_details}"

    # Fetch and summarize market news
    news_df = get_market_news()
    if news_df is not None:
        analyzed_news = analyze_market_news(news_df)
        if analyzed_news is not None:
            news_summary = "\n".join(analyzed_news['summary'].tolist())  # Summarize news
        else:
            news_summary = "No relevant market news available."
    else:
        news_summary = "No market news could be fetched."

    # System message to guide the AI model
    system_message = (
        f"Here is some market data: {market_conditions_str}. "
        f"The user has the following financial profile: {user_context}. "
        f"Additionally, here are the latest market news updates: {news_summary}. "
        "When responding, consider this user's financial goals, risk tolerance, and market data to provide personalized advice. "
        "Your tone should be friendly, supportive, and informative, much like a personal financial advisor who is also a friend."
    )

    try:
        # Sending the chat completion request
        chat_completion = client.chat.completions.create(model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional, emotionally intelligent, and friendly financial advisor named Audney. Your goal is to educate the user on their finances and provide tailored advice."},
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ])

        # Handle the API response
        if chat_completion.choices:
            answer = chat_completion.choices[0].message.content.strip()
            return answer
        else:
            return "No response from OpenAI."

    except Exception as e:
        print(f"Error calling OpenAI: {e}")
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

    # Check if the query is about stock price
    if any(keyword in user_input.lower() for keyword in ['price', 'ticker', 'how much']):
        company_name_or_symbol = extract_company_name(user_input)
        possible_matches = search_company_or_ticker(company_name_or_symbol)
        if len(possible_matches) == 1:
            # If exactly one match is found, fetch the stock price
            company_name, ticker_symbol = possible_matches[0]
            stock_price = get_stock_price(ticker_symbol)
            ticker_quote = f"Currently, {company_name} ({ticker_symbol}) is priced at {stock_price}."
            contains_html = False

            recent_time_threshold = timezone.now() - timedelta(seconds=5)  # Adjust as needed
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


        elif len(possible_matches) > 1:
            # If multiple matches are found, prompt the user to choose
            response_message = "I found multiple companies with that name, please choose the one you're referring to: "
            for name, ticker in possible_matches:
                response_message += f"<li><a href='#' onclick='fetchStockPrice(\"{ticker}\", \"{name}\")'>{name} ({ticker})</a></li>"
            response_message += "</ul>"
            contains_html = True

            logger.debug(f"contains_html value: {contains_html}")  # Assuming contains_html is the variable holding the value

            # Assuming user_input, user, and answer are available
            recent_time_threshold = timezone.now() - timedelta(seconds=5)  # Adjust the timedelta as needed
            existing_message = AudneyMessage.objects.filter(
                user=request.user,
                message=response_message,
                created_at__gte=recent_time_threshold
            ).exists()

            if not existing_message:
                AudneyMessage.objects.create(
                    user=request.user,
                    user_query=user_input,
                    message=response_message,
                    contains_html=contains_html,
                    message_type='audney',
                )
            else:
                logger.info("Duplicate message detected, not saving.")

        else:
            response_message = "Sorry, I couldn't find the stock price for the company you mentioned."
            contains_html = False

            logger.debug(f"contains_html value: {contains_html}")  # Assuming contains_html is the variable holding the value
            recent_time_threshold = timezone.now() - timedelta(seconds=5)  # Adjust the timedelta as needed
            existing_message = AudneyMessage.objects.filter(
                user=request.user,
                message=response_message,
                created_at__gte=recent_time_threshold
            ).exists()

            if not existing_message:
                AudneyMessage.objects.create(
                    user=request.user,
                    user_query=user_input,
                    message=response_message,
                    contains_html=contains_html,
                    message_type='audney',
                )
            else:
                logger.info("Duplicate message detected, not saving.")
    else:
        # Handle investment strategy or general queries using OpenAI API
        response = ask_openai(user_input, request.user)
        response_message = response if response else "Sorry, I couldn't understand your query."
        contains_html = False

        logger.debug(f"contains_html value: {contains_html}")  # Assuming contains_html is the variable holding the value

        # Check if a similar response has been generated recently
        recent_time_threshold = timezone.now() - timedelta(seconds=5)  # Adjust the timedelta as needed
        existing_message = AudneyMessage.objects.filter(
            user=request.user,
            message=response_message,
            created_at__gte=recent_time_threshold
        ).exists()

        if not existing_message:
            AudneyMessage.objects.create(
                user=request.user,
                user_query=user_input,
                message=response_message,
                contains_html=contains_html,
                message_type='audney',
            )
        else:
            logger.info("Duplicate message detected, not saving.")

    # Format the timestamp
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
    companyName = request.GET.get('companyName')

    if user.is_authenticated and symbol:
        try:
            price = get_stock_price(symbol)
            escaped_company_name = escape(companyName)

            StockPriceResponse.objects.create(
                user=user,
                query=f"Stock price check for {companyName} ({symbol})",
                ticker_quote=f"{companyName} is currently priced at {price}",
                message_type='system'

             ) # Indicating this is a system-generated response

            return JsonResponse({'success': True, 'price': price, 'companyName': escaped_company_name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'No symbol provided or user not authenticated'})

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
        new_username = request.POST.get('new_username')
        new_email = request.POST.get('new_email')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        financial_goals = request.POST.get('financial_goals')
        risk_tolerance = request.POST.get('risk_tolerance')
        income_level = request.POST.get('income_level')
        has_dependents = request.POST.get('has_dependents')
        savings_months = request.POST.get('savings_months')

        # Update username if it has changed
        if new_username and new_username != user.username:
            user.username = new_username
            user.save()
            messages.success(request, 'Username updated successfully.')

        # Update email if it has changed
        if new_email and new_email != user.email:
            user.email = new_email
            user.save()
            messages.success(request, 'Email updated successfully.')

        # Update password if it has changed and is confirmed
        if new_password1 and new_password1 == new_password2:
            user.set_password(new_password1)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated successfully.')

        # Update UserProfile fields
        if financial_goals:
            profile.financial_goals = financial_goals
        if risk_tolerance:
            profile.risk_tolerance = risk_tolerance
        if income_level:
            profile.income_level = income_level
        if has_dependents:
            profile.has_dependents = has_dependents
        if savings_months:
            profile.savings_months = savings_months
        profile.save()
        messages.success(request, 'Profile updated successfully.')

        return redirect('chatbot')

    return render(request, 'update_profile.html', {'user': user})

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

