from datetime import datetime
from flask import Flask, render_template, request, send_file, url_for, redirect
from . import app
from .services import CovidAppServices
import logging
import time
import os

services = CovidAppServices()

def log(message, type="info"):
    if type == "error":
        logging.error(message)
    else:
        #logging.info(message)
        print(message)

#To delete
@app.route("/")
def whatup():
    return redirect("https://www.novarad.net/", code=302)

#inp: dicom, outp: url  
# auth token in header
@app.route("/processImage", methods=["GET", "POST"])
def processImage(): #POST
    log("process image")
    if request.method == "POST":
        dicomImage = request.files["dicom"]
        ip_addr = request.remote_addr

        log("PROCESSING" + dicomImage.filename)
        path = app.root_path
        resultUrl, statusCode = services.processImage(path, dicomImage, ip_addr)

    else: #if it's a GET we'll just send them to novarad's homepage
        resultUrl = "https://www.novarad.net/"
    return resultUrl, statusCode #url for fetchReport

#fetches report (HTML)
#inp: access code, outp: html
@app.route("/fetchReport/<uid>")
def fetchReport(uid): #GET
    log("fetch image")
    info = services.getReportInfo(uid)
    status = "FINISHED"
    if isinstance(info, str): #if info == "EXPIRED" || "UNFINISHED"
        status = info
        info = {'currentTime' : datetime.now().strftime("%m/%d/%Y %H:%M")}
    return render_template("report.html", info=info, status=status)

@app.route("/downloadInstaller")
def downloadInstaller(): #GET
    log("HERE")
    ip_addr = request.remote_addr
    UID = "idk" # TODO either get uid or make one from hub info
    userID = "sars" #request.args.get("hubUserID")
    facility="idk where" #request.args.get("facility")
    services.saveUserID(userID, facility)
    exe_name = 'huangshan.jpg'#'novlogo.svg'
    url = services.getExeUrl(exe_name)
    #return send_file(os.path.join('static','images', exe_name), attachment_filename=exe_name) #can either return url or file- not sure if should save it to blob or webapp
    return redirect(url, code=302)