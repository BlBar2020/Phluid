from django.core.management.base import BaseCommand
import csv
from audney.models import Stock


class Command(BaseCommand):
    help = 'Imports stock tickers from a CSV file'

    def handle(self, *args, **options):
        csv_file_path = 'audney/stock_tickers.csv'
        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                Stock.objects.get_or_create(
                    company_name=row['Company Name'],
                    ticker_symbol=row['Ticker Symbol']
                )
        self.stdout.write(self.style.SUCCESS(
            'Successfully imported stock tickers'))
