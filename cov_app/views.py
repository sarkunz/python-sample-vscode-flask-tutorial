from datetime import datetime
from flask import Flask, render_template, request, send_file, url_for
from . import app
from .services import CovidAppServices
import logging
import time
import os

services = CovidAppServices()

#To delete
@app.route("/")
def whatup():
    return "nothing to see here"

#inp: dicom, outp: url  
# auth token in header
@app.route("/processImage", methods=["GET", "POST"])
def processImage(): #POST
    print("process image")
    if request.method == "POST":
        logging.info("START PROCESS IMAGE")
        startTime = time.time()
        
        dicomImage = request.files["dicom"]
        startprocess = time.time()
        print("STARTUP TIME: " + str(startprocess - startTime))
        # if(dicomImage.filename.find('.dcm') == -1):
        #     return "Invalid upload file type"
        print(dicomImage.filename)
        print("PROCESSING" + dicomImage.filename)
        path = app.root_path
        resultUrl, statusCode = services.processImage(path, dicomImage)
        print("PROCESS TIME " + str(startprocess- startTime))
        print("TOTOAL TIME" +  str(time.time() - startTime))

    else: #if it's a GET we'll just send them to novarad's homepage
        resultUrl = "https://www.novarad.net/"
    return resultUrl, statusCode #url for fetchReport

#fetches report (HTML)
#inp: access code, outp: html
@app.route("/fetchReport/<uid>")
def fetchReport(uid): #GET
    print("fetch image")
    info = services.getReportInfo(uid)
    status = "FINISHED"
    if isinstance(info, str): #if info == "EXPIRED" || "UNFINISHED"
        status = info
    return render_template("report.html", info=info, status=status)

@app.route("/downloadInstaller")
def downloadInstaller(): #GET
    print("HERE")
    userID = "sars" #request.args.get("hubUserID")
    facility="idk where" #request.args.get("facility")
    services.saveUserID(userID, facility)
    exe_name = 'novlogo.svg'
    #url = services.getExeUrl(exe_name)
    return send_file(os.path.join('static','images', exe_name), attachment_filename=exe_name)