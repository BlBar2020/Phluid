from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
import bleach

# Get a logger for this module
logger = logging.getLogger(__name__)

# Define a UserProfile model
class UserProfile(models.Model):
    # Define choices for the financial_goals field
    FINANCIAL_GOALS_CHOICES = [
        ('budgeting', 'Budgeting'),
        ('debt_management', 'Debt Management'),
        ('insurance_planning', 'Insurance Planning'),
        ('investment_management', 'Investment Management'),
        ('retirement_planning', 'Retirement Planning'),
        ('tax_planning', 'Tax Planning'),
        ('estate_planning', 'Estate Planning'),
        ('wealth_management', 'Wealth Management'),
    ]

    # New choices for the additional fields
    RISK_TOLERANCE_CHOICES = [
        ('aggressive', 'Aggressive'),
        ('moderate', 'Moderate'),
        ('conservative', 'Conservative'),
    ]

    INCOME_LEVEL_CHOICES = [
        ('55001_89000', '$55,001 - $89,000'),
        ('89001_150000', '$89,001 - $150,000'),
        ('150001_plus', '$150,001+'),
    ]

    DEPENDENTS_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]

    SAVINGS_MONTHS_CHOICES = [
        ('3_months', '3 months'),
        ('6_months', '6 months'),
        ('9_months', '9 months'),
        ('12_months', '12 months'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True, blank=True)
    financial_goals = models.CharField(max_length=50, choices=FINANCIAL_GOALS_CHOICES, blank=False)
    risk_tolerance = models.CharField(max_length=20, choices=RISK_TOLERANCE_CHOICES, blank=True, null=True)
    income_level = models.CharField(max_length=20, choices=INCOME_LEVEL_CHOICES, blank=True, null=True)
    has_dependents = models.CharField(max_length=3, choices=DEPENDENTS_CHOICES, blank=True, null=True)
    savings_months = models.CharField(max_length=10, choices=SAVINGS_MONTHS_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

# Receiver to create or update user profile upon user creation or update
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        instance.userprofile.save()


MESSAGE_TYPES = [
    ('user', 'User'),
    ('system', 'System'),
    ('audney', 'Audney'),
]

MESSAGE_TYPES = [
    ('user', 'User'),
    ('system', 'System'),
    ('audney', 'Audney'),
]

class UserMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_messages')
    message = models.TextField()
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES, default='user')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"User {self.user.username}: {self.message[:50]}"

class StockPriceResponse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stock_price_responses')
    query = models.TextField()  # What the user asked for, e.g., "stock price for Apple"
    ticker_quote = models.TextField()  # The actual stock price response
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES, default='system')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response to {self.user.username}: {self.ticker_quote[:50]}"

class AudneyMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audney_messages')
    message = models.TextField()
    user_query = models.TextField(blank=True, null=True)  # Optional field to store the user's query for context
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES, default='audney')
    contains_html = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Audney response to {self.user.username}: {self.message[:50]}"

    def save(self, *args, **kwargs):
        # Example: Sanitize the HTML content if contains_html is True
        if self.contains_html:
            self.message = bleach.clean(
                self.message,
                tags=['a', 'p', 'ul', 'li'],
                attributes={'a': ['href', 'class', 'data-ticker-symbol']},
                strip=True
            )

        super(AudneyMessage, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.message}"
    class Meta:
        app_label = 'audney'

# Define a MarketCondition model
class MarketCondition(models.Model):
    ticker = models.CharField(max_length=10)
    condition = models.CharField(max_length=10)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticker}: {self.condition}"

    class Meta:
        app_label = 'audney'

