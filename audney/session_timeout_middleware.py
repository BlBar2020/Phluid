from django.utils import timezone
from django.contrib.auth import logout
from django.conf import settings
from django.shortcuts import redirect
from datetime import timedelta

class SessionIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process for authenticated users
        if request.user.is_authenticated:
            now = timezone.now()
            session_timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 1800)  # Default to 30 minutes
            last_activity_str = request.session.get('last_activity')
            
            if last_activity_str:
                last_activity = timezone.datetime.fromisoformat(last_activity_str)
                # Calculate the time left before the session times out
                time_left = session_timeout - (now - last_activity).total_seconds()

                if time_left <= 0:
                    # If time left is zero or negative, logout the user and redirect to login page
                    logout(request)
                    # Redirect to the login page with a message
                    return redirect(f'/login?next={request.path}&timed_out=1')
                elif time_left <= 180:
                    # If time left is 3 minutes or less, flag for showing the warning modal
                    request.session['show_timeout_warning'] = True
                else:
                    # Reset the warning flag if more than 3 minutes left
                    request.session['show_timeout_warning'] = False

            # Update the last activity time in the session
            request.session['last_activity'] = now.isoformat()

        response = self.get_response(request)
        return response
