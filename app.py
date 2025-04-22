import os
import requests
import logging
import functools
import json # For parsing JSON responses/errors
from flask import Flask, request, render_template, abort, flash, get_flashed_messages, session, redirect, url_for
from dotenv import load_dotenv
from urllib.parse import urlparse
from requests.exceptions import RequestException
from werkzeug.security import generate_password_hash, check_password_hash

# --- Configuration ---
load_dotenv() # Load environment variables from .env

app = Flask(__name__)

# --- Secret Key Configuration (CRITICAL for session persistence) ---
flask_secret_key = os.environ.get("FLASK_SECRET_KEY")
if flask_secret_key:
    app.secret_key = flask_secret_key
    logging.info("Flask secret key loaded from FLASK_SECRET_KEY environment variable.")
else:
    app.secret_key = os.urandom(24)
    logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    logging.warning("!!! FLASK_SECRET_KEY environment variable not set.        !!!")
    logging.warning("!!! Falling back to a temporary, random secret key.       !!!")
    logging.warning("!!! User sessions (login state) WILL NOT PERSIST          !!!")
    logging.warning("!!! across application restarts or worker reloads.        !!!")
    logging.warning("!!! Set FLASK_SECRET_KEY in your .env file for proper     !!!")
    logging.warning("!!! session handling.                                     !!!")
    logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Credentials ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_PLAIN = os.getenv("ADMIN_PASSWORD")
ADMIN_PASSWORD_HASH = None

if not ADMIN_USERNAME or not ADMIN_PASSWORD_PLAIN:
    app.logger.error("FATAL: ADMIN_USERNAME or ADMIN_PASSWORD not found in environment variables.")
else:
    ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD_PLAIN)
    app.logger.info(f"Admin user '{ADMIN_USERNAME}' loaded.")

# --- Perplexica API Configuration ---
PERPLEXICA_API_URL = os.getenv("PERPLEXICA_API_URL")
PERPLEXICA_CHAT_PROVIDER = os.getenv("PERPLEXICA_CHAT_PROVIDER")
PERPLEXICA_CHAT_NAME = os.getenv("PERPLEXICA_CHAT_NAME")
PERPLEXICA_EMBEDDING_PROVIDER = os.getenv("PERPLEXICA_EMBEDDING_PROVIDER")
PERPLEXICA_EMBEDDING_NAME = os.getenv("PERPLEXICA_EMBEDDING_NAME")
# Optional custom OpenAI settings
PERPLEXICA_CUSTOM_OPENAI_BASE_URL = os.getenv("PERPLEXICA_CUSTOM_OPENAI_BASE_URL")
PERPLEXICA_CUSTOM_OPENAI_KEY = os.getenv("PERPLEXICA_CUSTOM_OPENAI_KEY")


if not PERPLEXICA_API_URL:
    app.logger.error("FATAL: PERPLEXICA_API_URL not found in environment variables.")
    # App can run, but API calls will fail
elif not all([PERPLEXICA_CHAT_PROVIDER, PERPLEXICA_CHAT_NAME, PERPLEXICA_EMBEDDING_PROVIDER, PERPLEXICA_EMBEDDING_NAME]):
    app.logger.warning("One or more Perplexica model details (Chat/Embedding Provider/Name) missing. API calls might fail if defaults are not accepted.")
else:
    app.logger.info(f"Perplexica API configured: URL='{PERPLEXICA_API_URL}', Chat='{PERPLEXICA_CHAT_PROVIDER}/{PERPLEXICA_CHAT_NAME}', Embedding='{PERPLEXICA_EMBEDDING_PROVIDER}/{PERPLEXICA_EMBEDDING_NAME}'")
    if PERPLEXICA_CUSTOM_OPENAI_BASE_URL:
        app.logger.info(f"Using Custom OpenAI Base URL: {PERPLEXICA_CUSTOM_OPENAI_BASE_URL}")


# --- Karakeep / Hoarder Configuration ---
KARAKEEP_API_URL = os.getenv("KARAKEEP_API_URL")
KARAKEEP_API_KEY = os.getenv("KARAKEEP_API_KEY")
KARAKEEP_LIST_NAME = os.getenv("KARAKEEP_LIST_NAME")
KARAKEEP_ENABLED = False

if all([KARAKEEP_API_URL, KARAKEEP_API_KEY, KARAKEEP_LIST_NAME]):
    KARAKEEP_API_URL = KARAKEEP_API_URL.rstrip('/')
    if not KARAKEEP_API_URL.endswith('/api/v1'):
         app.logger.warning(f"KARAKEEP_API_URL ('{KARAKEEP_API_URL}') does not seem to end with '/api/v1'. Ensure this is the correct base path.")
    KARAKEEP_ENABLED = True
    app.logger.info(f"Karakeep integration enabled. Target List: '{KARAKEEP_LIST_NAME}', API URL: '{KARAKEEP_API_URL}'")
else:
    app.logger.info("Karakeep integration details missing or incomplete. Sending to Karakeep is disabled.")


# --- Authentication Decorator ---
def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'logged_in' not in session:
            flash("Please log in to access this page.", "info")
            next_url = request.url
            return redirect(url_for('login', next=next_url))
        return view(**kwargs)
    return wrapped_view

# --- Helper Functions ---

def call_perplexica_api(query: str) -> dict | None:
    """Sends query to Perplexica API and returns the parsed JSON response."""
    if not PERPLEXICA_API_URL:
        app.logger.error("Perplexica API URL is not configured.")
        return None

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    payload = {
        "chatModel": {
            "provider": PERPLEXICA_CHAT_PROVIDER,
            "name": PERPLEXICA_CHAT_NAME,
        },
        "embeddingModel": {
            "provider": PERPLEXICA_EMBEDDING_PROVIDER,
            "name": PERPLEXICA_EMBEDDING_NAME,
        },
        "optimizationMode": "balanced", # Hardcoded as requested
        "focusMode": "webSearch",      # Hardcoded as requested
        "query": query,
        "stream": False # Hardcoded as requested
        # "history": [], # Add if needed later
        # "systemInstructions": "", # Add if needed later
    }

    # Add custom OpenAI details if provided
    if PERPLEXICA_CUSTOM_OPENAI_BASE_URL:
        payload["chatModel"]["customOpenAIBaseURL"] = PERPLEXICA_CUSTOM_OPENAI_BASE_URL
    if PERPLEXICA_CUSTOM_OPENAI_KEY:
        payload["chatModel"]["customOpenAIKey"] = PERPLEXICA_CUSTOM_OPENAI_KEY

    app.logger.info(f"Sending query to Perplexica API: {PERPLEXICA_API_URL}")
    app.logger.debug(f"Perplexica Request Payload: {json.dumps(payload)}") # Log payload for debugging

    try:
        response = requests.post(PERPLEXICA_API_URL, headers=headers, json=payload, timeout=120) # Increased timeout for potentially long searches
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        app.logger.info("Successfully received response from Perplexica API.")
        app.logger.debug(f"Perplexica Response Data: {json.dumps(response_data)}") # Log response for debugging
        return response_data

    except RequestException as e:
        app.logger.error(f"Error calling Perplexica API ({PERPLEXICA_API_URL}): {e}")
        error_details = "Network error or Perplexica API unreachable."
        if e.response is not None:
            error_details = f"Status Code: {e.response.status_code}. "
            try:
                error_json = e.response.json()
                error_details += f"Response: {json.dumps(error_json)}"
            except json.JSONDecodeError:
                error_details += f"Raw Response: {e.response.text[:500]}" # Log raw text if not JSON
        flash(f"Error communicating with Perplexica API: {error_details}", "error")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error processing Perplexica API call: {e}", exc_info=True)
        flash("An unexpected error occurred while contacting the Perplexica API.", "error")
        return None


def get_karakeep_list_id(api_url: str, api_key: str, list_name: str) -> str | None:
    """Fetches the ID of a Karakeep list by its name. (Adapted from summarizer_app)"""
    if not KARAKEEP_ENABLED:
        app.logger.warning("Karakeep is disabled, cannot fetch list ID.")
        return None

    list_endpoint_url = f"{api_url}/lists"
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    app.logger.info(f"Attempting to find Karakeep list ID for: '{list_name}' via GET {list_endpoint_url}")

    try:
        response = requests.get(list_endpoint_url, headers=headers, timeout=15)
        response.raise_for_status()
        response_data = response.json()

        actual_list_data = None
        if isinstance(response_data, list):
            actual_list_data = response_data
        elif isinstance(response_data, dict):
            possible_keys = ['data', 'results', 'items', 'lists']
            for key in possible_keys:
                if key in response_data and isinstance(response_data[key], list):
                    actual_list_data = response_data[key]
                    break
            if actual_list_data is None:
                 app.logger.error(f"Karakeep /lists response was a dictionary, but could not find list data under expected keys. Keys: {list(response_data.keys())}")
                 return None
        else:
            app.logger.error(f"Unexpected response format from Karakeep /lists endpoint. Expected list or dict, got: {type(response_data)}")
            return None

        if actual_list_data is not None:
            for lst in actual_list_data:
                if isinstance(lst, dict) and lst.get('name') == list_name:
                    list_id = lst.get('id')
                    if list_id:
                        app.logger.info(f"Found Karakeep list '{list_name}' with ID: {list_id}")
                        return str(list_id)
                    else:
                        app.logger.error(f"List '{list_name}' found but has no 'id' field: {lst}")
            app.logger.warning(f"Karakeep list named '{list_name}' not found in the response.")
            return None
        else:
             app.logger.error("Failed to extract actual list data from Karakeep response.")
             return None

    except RequestException as e:
        app.logger.error(f"Error requesting Karakeep lists from {list_endpoint_url}: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Error processing Karakeep lists response: {e}")
        return None

def send_result_to_karakeep(api_url: str, api_key: str, list_id: str, query: str, response_message: str) -> bool:
    """Sends the Perplexica query and response message to a specific Karakeep list."""
    if not KARAKEEP_ENABLED:
        app.logger.warning("Karakeep is disabled, cannot send result.")
        return False

    create_bookmark_url = f"{api_url}/bookmarks"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # Use the query as the title, response message as the text/body
    title = query[:255] # Truncate title if needed
    text_content = response_message

    # Step 1: Create the global bookmark
    create_payload = {
        "title": title,
        "text": text_content,
        "type": "text", # Store as text type
        "archived": False,
        "favourited": False,
        "url": None, # No specific source URL for the overall query result
        "note": f"Perplexica result for query: {query}",
    }
    app.logger.info(f"Attempting Step 1: POST result to Karakeep (Endpoint: {create_bookmark_url}), title '{title}'")

    try:
        response_create = requests.post(create_bookmark_url, headers=headers, json=create_payload, timeout=20)
        response_create.raise_for_status()
        created_bookmark_data = response_create.json()
        new_bookmark_id = created_bookmark_data.get('id')

        if not new_bookmark_id:
            app.logger.error(f"ERROR: Could not extract 'id' from POST /bookmarks response. Response: {str(created_bookmark_data)[:500]}...")
            return False

        new_bookmark_id = str(new_bookmark_id)
        app.logger.info(f"Successfully Step 1: Created Bookmark ID {new_bookmark_id}")

        # Step 2: Link the new bookmark to the target list
        link_url = f"{api_url}/lists/{list_id}/bookmarks/{new_bookmark_id}"
        app.logger.info(f"Attempting Step 2: Link Bookmark ID {new_bookmark_id} to List ID {list_id} (PUT {link_url})")

        response_link = requests.put(link_url, headers=headers, json={}, timeout=15)
        response_link.raise_for_status()

        app.logger.info(f"Successfully Step 2: Linked Bookmark ID {new_bookmark_id} to List ID {list_id}. Status: {response_link.status_code}")
        return True

    except RequestException as e:
        failed_url = e.request.url if e.request else "Unknown URL"
        failed_method = e.request.method if e.request else "Unknown Method"
        app.logger.error(f"Error during Karakeep interaction ({failed_method} {failed_url}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Response Status: {e.response.status_code}")
            try:
                error_details = e.response.json()
                app.logger.error(f"Response JSON: {error_details}")
            except Exception:
                app.logger.error(f"Raw Response Text: {e.response.text[:500]}...")
        return False
    except Exception as e:
        app.logger.error(f"Unexpected error during Karakeep result sending: {e}", exc_info=True)
        return False


# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if 'logged_in' in session:
        flash("You are already logged in.", "info")
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        next_url = request.form.get('next')

        if ADMIN_PASSWORD_HASH and username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['logged_in'] = True
            session['username'] = username
            app.logger.info(f"User '{username}' logged in successfully.")
            flash(f"Welcome back, {username}!", "success")

            if next_url and urlparse(next_url).netloc == urlparse(request.host_url).netloc:
                 app.logger.info(f"Redirecting logged in user to intended destination: {next_url}")
                 return redirect(next_url)
            else:
                 app.logger.info(f"Redirecting logged in user to index (no valid 'next' URL).")
                 return redirect(url_for('index'))
        else:
            app.logger.warning(f"Failed login attempt for username: {username}")
            flash("Invalid username or password.", "error")

    return render_template('login.html', next=request.args.get('next', ''))


@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('logged_in', None)
    session.pop('username', None)
    app.logger.info("User logged out.")
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Handles displaying the query form and processing submissions."""
    if request.method == 'POST':
        query = request.form.get('query')
        send_to_karakeep_checked = 'send_to_karakeep' in request.form
        session['send_to_karakeep_enabled'] = send_to_karakeep_checked
        app.logger.info(f"Received query via POST: '{query}'")
        app.logger.info(f"Saved 'Send to Karakeep' option to session: {send_to_karakeep_checked}")

        if not query:
            flash("Please enter a query.", "error")
            # Re-render index with current checkbox state
            return render_template('index.html', username=session.get('username'), send_to_karakeep_checked=send_to_karakeep_checked)

        # Call Perplexica API
        perplexica_response = call_perplexica_api(query)

        if perplexica_response and 'message' in perplexica_response:
            message = perplexica_response.get('message', 'No message content received.')
            sources = perplexica_response.get('sources', []) # Default to empty list

            # Send to Karakeep if enabled and successful
            karakeep_sent_ok = None
            if session.get('send_to_karakeep_enabled'):
                app.logger.info(f"Karakeep option is enabled for query '{query}'. Attempting to send.")
                if KARAKEEP_ENABLED:
                    karakeep_list_id = get_karakeep_list_id(KARAKEEP_API_URL, KARAKEEP_API_KEY, KARAKEEP_LIST_NAME)
                    if karakeep_list_id:
                        karakeep_sent_ok = send_result_to_karakeep(
                            KARAKEEP_API_URL, KARAKEEP_API_KEY, karakeep_list_id,
                            query, message # Send query as title, message as body
                        )
                        if karakeep_sent_ok:
                            app.logger.info(f"Successfully sent result for query '{query}' to Karakeep list '{KARAKEEP_LIST_NAME}'.")
                            # Optional: flash("Result sent to Karakeep.", "success")
                        else:
                            app.logger.error(f"Failed to send result for query '{query}' to Karakeep list '{KARAKEEP_LIST_NAME}'.")
                            flash("Failed to send result to Karakeep.", "error") # Notify user of Karakeep failure
                    else:
                        app.logger.error(f"Could not find Karakeep list ID for '{KARAKEEP_LIST_NAME}'. Cannot send result.")
                        flash(f"Could not find Karakeep list '{KARAKEEP_LIST_NAME}'. Result not sent.", "error")
                        karakeep_sent_ok = False
                else:
                    app.logger.warning("Karakeep sending skipped: Integration is disabled in config.")
                    flash("Karakeep integration is disabled. Result not sent.", "warning")
                    karakeep_sent_ok = False
            else:
                 app.logger.info(f"Karakeep option is NOT enabled for query '{query}'.")


            # Render results page
            app.logger.info(f"Successfully processed query: '{query}'")
            return render_template('results.html',
                                   query=query,
                                   message=message,
                                   sources=sources,
                                   username=session.get('username'))
        else:
            # Error handled by call_perplexica_api flashing message
            app.logger.error(f"Failed to get valid response from Perplexica for query: '{query}'")
            # Re-render index page with the submitted query and checkbox state
            return render_template('index.html',
                                   submitted_query=query,
                                   username=session.get('username'),
                                   send_to_karakeep_checked=send_to_karakeep_checked)

    # For GET request, just display the form
    send_to_karakeep_checked = session.get('send_to_karakeep_enabled', False) # Get current state or default
    return render_template('index.html', username=session.get('username'), send_to_karakeep_checked=send_to_karakeep_checked)


# Optional: Health check endpoint
@app.route('/health')
def health_check():
    return "OK", 200


if __name__ == '__main__':
    # Not used by Gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True)