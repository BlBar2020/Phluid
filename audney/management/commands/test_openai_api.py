from django.core.management.base import BaseCommand
import openai
import logging
from django.conf import settings

class Command(BaseCommand):
    help = 'Tests the OpenAI API integration'

    def handle(self, *args, **options):
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # Print the API key and library version to check correct values are loaded
        logger.info(f"Current OpenAI API Key: {settings.OPENAI_API_KEY}")
        logger.info(f"Using openai library version: {openai.__version__}")

        try:
            # Ensure the API key is set

            # Make a simple API call to test
            response = client.chat.completions.create(
                model="gpt-4",
                prompt="Hello, world!",
                max_tokens=5
            )

            # Log successful connection
            logger.info('Successfully connected to OpenAI API.')
            logger.info(f"Response: {response}")

            # Use Django's command line style success message
            self.stdout.write(self.style.SUCCESS('Successfully connected to OpenAI API. Response:'))
            self.stdout.write(str(response))
        except Exception as e:
            # Log and print the error
            logger.error(f"Failed to connect to OpenAI API: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Failed to connect to OpenAI API: {e}"))
