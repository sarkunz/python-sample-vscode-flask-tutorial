from flask import Flask  # Import the Flask class


def create_app():
    app = Flask(__name__)    # Create an instance of the class for our use

    app.config.from_pyfile('settings.py')
    return app

app = create_app()