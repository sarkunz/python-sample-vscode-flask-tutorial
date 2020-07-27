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
@app.route("/processImage")#, method="POST")
def processImage(): #POST
    logger.info("START PROCESS IMAGE")
    #check for valid token (from header)
    services = CovidAppServices()
    # token = "token" #request.headers.get('authtoken')
    # validAuthToken = services.isValidToken(token)
    # if not validAuthToken:
    #     return False
    
    # #call service to process dicom and return URL
    dicomImage = "dicom" #request.files["dicomImage"]
    path = app.root_path
    print("START SERVICE")
    # result = services.processImage(path, dicomImage)

    return "DONE" #result #accessCode

#fetches report (HTML)
#inp: access code, outp: html
@app.route("/fetchReport/<accessCode>")
def fetchReport(accessCode): #GETI 
    #accessCode = #request.data["accessCode"]
    print(accessCode)
    info = CovidAppServices().getReportInfo(accessCode)
    return render_template("report.html", info=info)

#PROBS NOT DOING THIS
#inp: certificate, outp: auth token
@app.route("/authenticate")
def authenticate(): #GET
    #read cert
    #generate auth token
    #save auth to db- assoc with study??

    #POSSIBLY reroute to '/fetchReport/<authtoken>'
    return "authenticate"

