from flask import Flask  # Import the Flask class
from logging import StreamHandler

app = Flask(__name__)    # Create an instance of the class for our use


# keep stdout/stderr logging using StreamHandler
streamHandler = StreamHandler()
app.logger.addHandler(streamHandler)