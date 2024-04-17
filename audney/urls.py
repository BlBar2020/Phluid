from django.urls import path, include
from .views import get_chat_history
from .views import audney, chatbot_response, login, register, logout, get_stock_price_view, update_profile, support, support_success

urlpatterns = [
    path('', audney, name='chatbot'),
    path('chat/response/', chatbot_response, name='chatbot_response'),
    path('login', login, name='login'),
    path('register', register, name='register'),
    path('logout', logout, name='logout'),
    path('get_stock_price/', get_stock_price_view, name='get_stock_price'),
    path('update_profile/', update_profile, name='update_profile'),
    path('chat/history/', get_chat_history, name='get_chat_history'),
    path('support/', support, name='support'),
    path('support/success/<str:from_page>/', support_success, name='support_success'),
]
