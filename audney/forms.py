from django import forms
from django.contrib.auth.models import User
from .models import UserProfile

# RegistrationForm to handle user registration, including date of birth
class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label='Confirm Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        labels = {
            'username': 'Username',
            'email': 'Email',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    # Add date of birth field
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        label="Date of Birth"
    )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


# UserForm to handle username, email, and password updates
class UserForm(forms.ModelForm):
    password1 = forms.CharField(
        label='New Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        required=False
    )
    password2 = forms.CharField(
        label='Confirm New Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        labels = {
            'username': 'Username',
            'email': 'Email',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'username': 'Requirements: 150 characters or fewer. Letters, digits, and @/./+/-/_ only.',
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super(UserForm, self).save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


# UserProfileForm to handle user profile-related fields (excluding date_of_birth)
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'city', 'state', 'financial_goals', 'experience_level', 
            'risk_tolerance', 'income_level', 'has_dependents', 'savings_months'
        ]
        labels = {
            'city': 'City',
            'state': 'State',
            'financial_goals': 'What is your financial goal?',
            'experience_level': 'What is your level of experience?',
            'risk_tolerance': 'What is your risk tolerance level?',
            'income_level': 'What is your income level?',
            'has_dependents': 'Do you have any dependents?',
            'savings_months': 'How many months worth of income do you have in your emergency savings?',
        }
        widgets = {
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.Select(attrs={'class': 'form-control'}),
            'financial_goals': forms.Select(attrs={'class': 'form-control'}),
            'experience_level': forms.Select(attrs={'class': 'form-control'}),
            'risk_tolerance': forms.Select(attrs={'class': 'form-control'}),
            'income_level': forms.Select(attrs={'class': 'form-control'}),
            'has_dependents': forms.Select(attrs={'class': 'form-control'}),
            'savings_months': forms.Select(attrs={'class': 'form-control'}),
        }


# SupportForm for user support
class SupportForm(forms.Form):
    email = forms.EmailField(
        required=False, 
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    subject = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(SupportForm, self).__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.fields['email'].required = False
            self.fields['email'].widget = forms.HiddenInput()
        else:
            self.fields['email'].required = True

