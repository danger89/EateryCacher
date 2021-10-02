'''create_server.py
Offers an interface to create a server handling the API.
'''

import logging
from configparser import ConfigParser
from shared_code import CONFIG_FILEPATH
from flask import Flask

#Logging
logger = logging.getLogger(__name__)

def create_app():
    '''Function for creating an app that can be ran
    using the Flask server (or any other WSGI server).'''
    logger.info("Creating app...")
    #Create a basic app
    app = Flask(__name__)
    #Register the server blueprint
    logger.info("Registering blueprint...")
    from server import app as server_blueprint
    #Register server routes
    app.register_blueprint(server_blueprint)
    logger.info("Blueprint registered. Returning app...")
    return app #Return the created app

#Read the configuration
logger.info("Reading configuration...")
config = ConfigParser()
config.read(CONFIG_FILEPATH)
logger.debug("Config file read.")
server_config = config["server"] #Get server config
#(NOTE: server options below only affects the default Flask server environment)
server_host = server_config["host"]
server_port = int(server_config["port"])
run_in_debug = server_config["debug"]
run_server = config.getboolean("server", "run_using_default_server") #Whether the server should be ran using the default Flask server (load this as a boolean value)

logger.info("Config read.")

if run_server == True:
    logger.info("Server should be ran. Running...")
    logger.warning("""WARNING!
    You are running the Flask default server. Only do this in a development
    environment! For production use, use a WSGI server like Gunicorn instead.
    (disable running the server by setting server/run_using_flask in the 
    configuration file to false)""")
    app = create_app()
    app.run(host=server_host, port=server_port, debug=run_in_debug)
else:
    logger.info("Server should not be ran from the server.py script.")
