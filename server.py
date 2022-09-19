'''server.py
Provides an API interface/server that allows one to retrieve menu data.
Uses Flask as a backend.
'''
from flask import Blueprint, jsonify, send_from_directory, render_template
from shared_code import read_json_from_file, cached_data_filepath, EATERY_KISTA_NOD_MENU_ID, CONFIG_FILEPATH, statistics_data_file_path, write_json_to_file, read_json_from_file, get_now
from menuparser import day_names_to_json_keys
from http import HTTPStatus
import logging, datetime, pytz, os
from configparser import ConfigParser
from dateutil.relativedelta import relativedelta

#Logging
logger = logging.getLogger(__name__)

app = Blueprint(__name__, "server")

#Load the configuration file
logger.info("Loading configuration file...")
config = ConfigParser()
config.read(CONFIG_FILEPATH) #Read the configuration filepath
logger.info("Configuration file loaded. Loading parameters...")
SHOW_INDEX_FILE = config["server"]["show_index"] if "show_index" in config["server"] else False #Load whether to show the index page or not
saved_menus = config["downloader"]["save_menus"] #This is used for the index file
HOST_EMAIL_ADDRESS = config["server"]["host_email"] if "host_email" in config["server"] else None #Load contact email to server host
STATISTICS_FILE_ENABLED = config["server"]["track_statistics"] if "track_statistics" in config["server"] else True #Check whether to track statistics from the API or not
CUSTOM_INDEX_FILE = config["server"]["custom_index_file"] if "custom_index_file" in config["server"] else None #Load a custom index file if configured

if HOST_EMAIL_ADDRESS == None:
    logger.warning("Warning! You have not added or set HOST_EMAIL_ADDRESS in your configuration. This is highly recommended to avoid the API being taken down and will probably be required in the future.")

if STATISTICS_FILE_ENABLED:
    logger.info("Statistics tracking from the API has been enabled. Statistics from the API will be tracked and saved.")
    #Check if the statistics file has been crated. If not, create it
    if not os.path.exists(statistics_data_file_path):
        logger.info("Creating statistics file...")
        DEFAULT_STATISTICS_JSON = {
            "requests": {
                "all_time": {
                    "count": 0,
                    "refreshed": str(get_now())
                },
                "weekly": {
                    "count": 0,
                    "refreshed": str(get_now())
                },
                "monthly": {
                    "count": 0,
                    "refreshed": str(get_now())
                },
                "daily": {
                    "count": 0,
                    "refreshed": str(get_now())
                },
            }
        }
        write_json_to_file(DEFAULT_STATISTICS_JSON, statistics_data_file_path)
        logger.info("Statistics file created.")
else:
    logger.info("Statistics tracking from the API has been disabled. Statistics from the API will not be tracked.")

def generate_api_response(status, content, status_code=200):
    '''Function for generating an API response following the response format
    (status and content).

    :param status: The status as a text.

    :param content: The request content (as a dictionary)

    :param status_code: The status code.'''
    logger.info(f"Creating API response with status {status}, status code {status_code}...")
    response = content
    response["status"] = status
    response["status_code"] = status_code
    return response #Return the response

def generate_api_error_response(error_message, status_code):
    '''Function for generating an API error.

    :param error_message: The error message to return.

    :param status_code: The status code to return.'''
    return generate_api_response("error", {"message": error_message}, status_code)

def generate_api_response_for(menu_name, week_number, day_number=None):
    '''Generates an API response for a specific menu ID and a
    specific week number.'''
    logger.info(f"Generating API response for menu id {menu_name}, week day {week_number}...")
    #Detect - string or integer
    is_digit = menu_name.isdigit()
    if not is_digit and not menu_name.startswith("/"): #This is done to match the format of the configuration files. It's not smart to have slashes to fill out the ID in a URL :)
        menu_name = f"/{menu_name}"
    elif is_digit:
        menu_name = int(menu_name)
    #Grab menu data
    menu_data = read_json_from_file(cached_data_filepath)
    logger.debug(f"Menu data: {menu_data}")
    #If the requested menu ID is a string, we can simply retrieve it right away. If not, we have to try to find the menu string that belongs to the menu ID
    if is_digit:
        logger.info("Trying to find menu ID...")
        found_menu_name = None
        for individual_menu_name, individual_menu_data in menu_data["cached_menus"].items():
            if "menu_id" in individual_menu_data and individual_menu_data["menu_id"] == menu_name:
                logger.info("Found menu ID.")
                found_menu_name = individual_menu_name
                menu_name = found_menu_name
        if found_menu_name is None:
            logger.info("Requested menu ID was not found.")
            return generate_api_error_response("Menu ID not available (menu ID was not found on the server - to (possibly) prevent this in the future you can use the API string ID instead). Refer to the documentation for more information.", HTTPStatus.NOT_FOUND)
    #Retrieve menu
    if menu_name in menu_data["cached_menus"]:
        logger.info("Menu is available. Checking if requested week is available...")
        requested_menu = menu_data["cached_menus"][str(menu_name)]
        if requested_menu["menu"]["week_number"] != week_number and requested_menu["menu"]["week_number"] != None:
            logger.info("Menu is not available.")
            return generate_api_error_response("Menu for requested week is not available.", HTTPStatus.NOT_FOUND)
        else:
            logger.info("Menu is available. Returning response...")
            #If a specific day hasn't been requested...
            if day_number == None:
                return generate_api_response("success", requested_menu) #...return the full menu
            else:
                logger.debug("Custom day has been specified! Checking and returning...")
                if day_number > len(day_names_to_json_keys): #If the passed day number is not in the list of keys (there should be error-checking for this implemented in the server, so unless this function is called externally, this error should not be triggered)
                    logger.warning("Invalid length passed!")
                    return generate_api_error_response("Unknown day number passed.", HTTPStatus.BAD_REQUEST)
                else:
                    requested_day_key = list(day_names_to_json_keys.values())[day_number-1]
                    logger.info(f"Requested day: {requested_day_key}")
                logger.debug("Checking for existence of the requested day..")
                if requested_day_key not in requested_menu["menu"]["days"]:
                    logger.info("Custom day is not available!")
                    return generate_api_error_response("Requested day is not available.", HTTPStatus.BAD_REQUEST)
                else:
                    logger.info("Custom day is available!")
                    return generate_api_response("success", {requested_menu["menu"]["days"][requested_day_key]}) #Get the menu for that day
    else:
        logger.info("Menu is not available. Returning error response...")
        return generate_api_error_response("Menu is not available.", HTTPStatus.NOT_FOUND)

def timestamp_to_local_time(timestamp_str):
    '''Converts a timestamp from a timestamp string to local Swedish time.'''
    return datetime.datetime.fromisoformat(timestamp_str).astimezone(tz=pytz.timezone("Europe/Stockholm"))

def increase_statistics_file_api_count():
    '''There is a statistics file which tracks how often the API has been accessed.
    This function can write to it.'''

    if STATISTICS_FILE_ENABLED:
        logger.debug("Updating API statistics...")
        logger.debug("Loading and updating statistics...")
        statistics_data = read_json_from_file(statistics_data_file_path)
        requests_data = statistics_data["requests"]
        STATISTICS_FUNCTIONS_ROTATE = {
            "all_time": lambda x: False,
            "weekly": lambda now: relativedelta(now, timestamp_to_local_time(requests_data["weekly"]["refreshed"])).weeks >= 1,
            "monthly": lambda now: relativedelta(now, timestamp_to_local_time(requests_data["monthly"]["refreshed"])).months >= 1,
            "daily": lambda now: relativedelta(now, timestamp_to_local_time(requests_data["daily"]["refreshed"])).days >= 1,
        } #Functions to check if data should be rotated or not.
        # Rotate statistics data if needed
        logger.info("(Possibly) rotating statistics data...")
        now = get_now()
        for statistics_key, statistics_function in STATISTICS_FUNCTIONS_ROTATE.items():
            #Evaluate
            if STATISTICS_FUNCTIONS_ROTATE[statistics_key](now):
                logger.info(f"Rotating statistics {statistics_key}...")
                statistics_data["requests"][statistics_key] = {"count": 0, "refreshed": str(now)}
                logger.info(f"{statistics_key} rotated in memory.")
        # Increase request counts by one
        for key in statistics_data["requests"].keys():
            statistics_data["requests"][key]["count"] += 1
        logger.info("Writing updated statistics...")
        write_json_to_file(statistics_data, statistics_data_file_path)


#Static endpoints
if SHOW_INDEX_FILE:
    @app.route("/")
    def index():
        '''Index page.'''
        logger.info("Got a request to the index. Returning...")
        statistics_data = read_json_from_file(statistics_data_file_path) if STATISTICS_FILE_ENABLED else None #Load statistics data
        return render_template("index.html" if not CUSTOM_INDEX_FILE else CUSTOM_INDEX_FILE,
                               saved_menus_list=config["downloader"]["save_menus"],
                               default_menu_id=EATERY_KISTA_NOD_MENU_ID,
                               host_email_address=HOST_EMAIL_ADDRESS,
                               statistics_data=statistics_data)
else:
    logger.info("Not registering index file since it has been configured not to be set.")

#API endpoints
@app.route("/api/")
def api():
    '''General API. Returns the Eatery Kista Nod menu
    for the current week.'''
    logger.info("Got a request to the general API! Generating response...")
    increase_statistics_file_api_count()
    #Get current week
    current_week = datetime.datetime.now(tz=pytz.timezone("Europe/Stockholm")).isocalendar()[1]
    logger.info(f"Current week: {current_week}")
    #Generate response
    response = generate_api_response_for(EATERY_KISTA_NOD_MENU_ID, current_week)
    logger.info(f"Response retrieved: {response}. Returning...")
    return jsonify(response), response["status_code"] #Return the response

@app.route("/api/<string:menu_id>/<int:week_number>")
def specific_api(menu_id, week_number):
    '''Specific API. Allows one to specify the menu ID and the week number.'''
    logger.info("Got a request to the specific API! Generating response...")
    increase_statistics_file_api_count()
    #Generate response
    response = generate_api_response_for(menu_id, week_number)
    logger.info(f"Response retrieved: {response}. Returning...")
    return jsonify(response), response["status_code"] #Return the response


@app.route("/api/<string:menu_id>/<int:week_number>/<int:day_number>")
def specific_day_api(menu_id, week_number, day_number):
    '''Specific day API. Allows one to specify the menu ID, the week number, and the day ID to retrieve.'''
    logger.info("Got a request to the specific day API! Generating response...")
    increase_statistics_file_api_count()
    #Validate the day ID
    if day_number < 1 or day_number > 7:
        logger.info(f"Invalid day number sent ({day_number}). Returning error...")
        return generate_api_error_response("Invalid day number (must be 1-7)", HTTPStatus.BAD_REQUEST), HTTPStatus.BAD_REQUEST
    logger.debug("Day number is valid. Generating response...")
    #Generate response
    response = generate_api_response_for(menu_id, week_number, day_number)
    logger.info(f"Response retrieved: {response}. Returning...")
    return jsonify(response), response["status_code"] #Return the response
