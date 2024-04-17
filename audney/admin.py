from django.contrib import admin
from .models import UserMessage, AudneyMessage, StockPriceResponse

class UserMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'created_at')
    search_fields = ['message']

class AudneyMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'user_query', 'contains_html', 'created_at')
    search_fields = ['message']
    list_filter = ['contains_html']

class StockPriceResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'query', 'ticker_quote', 'created_at')
    search_fields = ['query', 'response']

# Register your models here.
admin.site.register(UserMessage, UserMessageAdmin)
admin.site.register(AudneyMessage, AudneyMessageAdmin)
admin.site.register(StockPriceResponse, StockPriceResponseAdmin)
