from datetime import datetime
from flask import Flask, render_template, request
from . import app
from .services import CovidAppServices

import logging
from logging import StreamHandler

logger = logging.getLogger(__name__)
streamHandler = StreamHandler()
logger.addHandler(streamHandler)
logger.setLevel(logging.DEBUG)


#To delete
@app.route("/")
def whatup():
    return "Heyyyyyy"

#inp: dicom, outp: url  
# auth token in header
@app.route("/processImage", methods=["GET", "POST"])
def processImage(): #POST
    print("process image")
    if request.method == "POST":
        logger.info("START PROCESS IMAGE")

        services = CovidAppServices()
        
        #print(dicomImage)
        print("here")
        dicomImage = request.files["dicom"]
        if(dicomImage.filename.find('.dcm') == -1):
            return "Invalid upload file type"
        print("PROCESSING", dicomImage.filename)
        path = app.root_path
        result = services.processImage(path, dicomImage)
        print(result)

    else:
        result = "Novarad Home Page"
    return result #result #accessCode

#fetches report (HTML)
#inp: access code, outp: html
@app.route("/fetchReport/<accessCode>")
def fetchReport(accessCode): #GET
    #accessCode = #request.data["accessCode"]
    print(accessCode)
    info = CovidAppServices().getReportInfo(accessCode)
    return render_template("report.html", info=info)

