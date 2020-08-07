from datetime import datetime
from flask import Flask, render_template, request
from . import app
from .services import CovidAppServices
import logging

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
        print("START PROCESS IMAGE")
        services = CovidAppServices()
        
        #print(dicomImage)
        dicomImage = request.files["dicom"]
        # if(dicomImage.filename.find('.dcm') == -1):
        #     return "Invalid upload file type"
        print(dicomImage.filename)
        logging.info("PROCESSING" + dicomImage.filename)
        path = app.root_path
        result = services.processImage(path, dicomImage)

    else:
        result = "Novarad Home Page"
    return result #url for fetchReport

#fetches report (HTML)
#inp: access code, outp: html
@app.route("/fetchReport/<uid>")
def fetchReport(uid): #GET
    print("fetch image")
#accessCode = #request.data["accessCode"]
    info = CovidAppServices().getReportInfo(uid)
    status = "FINISHED"
    if isinstance(info, str): #if info == "EXPIRED" || "UNFINISHED"
        status = info
    return render_template("report.html", info=info, status=status)

