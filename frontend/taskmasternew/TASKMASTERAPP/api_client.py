import requests
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.base_url = 'http://localhost:8080'  # Update this with your Flask backend URL
        self.session = requests.Session()
        # Set default headers for CORS and JSON
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'  # This helps identify AJAX requests
        })

    def _handle_response(self, response):
        try:
            logger.info(f"API Response - Status: {response.status_code}, URL: {response.url}")
            logger.debug(f"Response Headers: {dict(response.headers)}")
            
            # Store session cookies if present in the response
            if response.cookies:
                self.session.cookies.update(response.cookies)
            
            # Check if response is JSON
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                data = response.json()
                logger.debug(f"Response Data: {json.dumps(data, indent=2)}")
                return data
            else:
                logger.error(f"Unexpected content type: {content_type}")
                logger.error(f"Response text: {response.text[:200]}...")  # Log first 200 chars
                return {'message': 'Invalid response format from server'}
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response: {response.text[:200]}...")  # Log first 200 chars
            return {'message': 'Invalid response from server'}

    def _make_request(self, method, endpoint, **kwargs):
        try:
            url = f'{self.base_url}{endpoint}'
            logger.info(f"Making {method} request to {url}")
            logger.debug(f"Request method: {method}")
            logger.debug(f"Request URL: {url}")
            logger.debug(f"Request headers: {self.session.headers}")
            logger.debug(f"Request data: {kwargs.get('json', {})}")
            
            response = self.session.request(method, url, **kwargs)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return {'message': f'Request failed: {str(e)}'}

    def register(self, data):
        logger.info(f"Registering user: {data['username']}")
        return self._make_request('POST', '/api/auth/register', json=data)

    def login(self, data):
        logger.info(f"Logging in user: {data['username']}")
        response = self._make_request('POST', '/api/external-login', json=data)
        if response.get('message') == 'Login successful':
            logger.info("Login successful, updating session cookies")
            # Store the session cookie
            self.session.cookies.update(response.get('cookies', {}))
        return response

    def logout(self):
        logger.info("Logging out user")
        response = self._make_request('POST', '/api/auth/logout')
        self.session.cookies.clear()
        return response

    def get_tasks(self, filters=None):
        logger.info(f"Getting tasks with filters: {filters}")
        params = filters or {}
        return self._make_request('GET', '/api/tasks', params=params)

    def get_users(self):
        logger.info("Getting all users")
        return self._make_request('GET', '/api/users')

    def get_task(self, task_id):
        logger.info(f"Getting task: {task_id}")
        return self._make_request('GET', f'/api/tasks/{task_id}')

    def create_task(self, data):
        logger.info(f"Creating task: {data['title']}")
        return self._make_request('POST', '/api/tasks', json=data)

    def update_task(self, task_id, data):
        logger.info(f"Updating task: {task_id}")
        return self._make_request('PUT', f'/api/tasks/{task_id}', json=data)

    def delete_task(self, task_id):
        logger.info(f"Deleting task: {task_id}")
        return self._make_request('DELETE', f'/api/tasks/{task_id}')

    def toggle_task(self, task_id):
        logger.info(f"Toggling task status: {task_id}")
        return self._make_request('POST', f'/api/tasks/{task_id}/toggle')

# Create a singleton instance
api_client = APIClient()