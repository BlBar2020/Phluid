# Import necessary modules from Django
from django import forms
from django.forms import ModelForm, DateInput
from django.contrib.auth.models import User
from .models import UserProfile
from django.core.exceptions import ValidationError
import re

# Define a UserForm form
class UserForm(forms.ModelForm):
    # Define password fields with labels and set their widget to PasswordInput
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(
        label='Confirm Password', widget=forms.PasswordInput)

    class Meta:
        # Specify the model to use
        model = User
        # Specify the fields to include in the form
        fields = ['username', 'email', 'first_name', 'last_name']

    # Validate the password1 field
    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        # Check if the password is strong
        if not self.is_strong_password(password1):
            # If not, raise a validation error
            raise ValidationError("Password is not strong enough")
        return password1

    # Validate the password2 field
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        # Check if the passwords match
        if password1 and password2 and password1 != password2:
            # If not, raise a validation error
            raise ValidationError("Passwords don't match")
        return password2

    # Check if a password is strong
    def is_strong_password(self, password):
        # Check various conditions for a strong password
        if len(password) < 8:
            return False
        if not re.search("[a-z]", password):
            return False
        if not re.search("[A-Z]", password):
            return False
        if not re.search("[0-9]", password):
            return False
        if not re.search("[!@#$%^&*(),.?\":{}|<>]", password):
            return False
        return True

    # Save the form data to the model
    def save(self, commit=True):
        user = super(UserForm, self).save(commit=False)
        # Set the user's password
        user.set_password(self.cleaned_data["password1"])
        if commit:
            # Save the user
            user.save()
        return user

# Define a UserProfileForm form
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['date_of_birth', 'financial_goals', 'risk_tolerance', 'income_level', 'has_dependents', 'savings_months']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'financial_goals': forms.Select(attrs={'class': 'form-control'}),
            'risk_tolerance': forms.Select(attrs={'class': 'form-control'}),
            'income_level': forms.Select(attrs={'class': 'form-control'}),
            'has_dependents': forms.Select(attrs={'class': 'form-control'}),
            'savings_months': forms.Select(attrs={'class': 'form-control'}),
        }

# forms.py
from django import forms

class SupportForm(forms.Form):
    email = forms.EmailField(required=False)  # Make email optional
    subject = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Pop the user from the passed kwargs
        super(SupportForm, self).__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.fields['email'].required = False  # User is logged in; don't require email
            self.fields['email'].widget = forms.HiddenInput()  # Hide the email field
        else:
            self.fields['email'].required = True  # User is not logged in; require email

