# services- business logic of API
from . import app
from datetime import datetime
import pydicom
import os
from .models import CovidAppModel
import numpy as np
import logging
import uuid
import requests
import json

def log(message, type="info"):
    if type == "error":
        logging.error(message)
    else:
        #logging.info(message)
        print(message)

def retError(code, message):
    log(message, "error")
    return message, code

class CovidAppServices:
    def __init__(self):
        self.model = CovidAppModel()

    def getHounsfieldUnits(self, dicom):
        data = dicom.pixel_array
        correctedSlope = 1 if dicom.RescaleSlope < 1 else dicom.RescaleSlope
        #correctedSlope = 1 if (dicom.RescaleSlope == 0) else dicom.RescaleSlope
        data = (data * correctedSlope) + dicom.RescaleIntercept
        data = np.clip(data,a_min=-2000,a_max=None)
        return data

    #yyyymmdd -> mm/dd/yyyy
    def formatDate(self, date):
        return date[4:6] + "/" + date[6:8] + "/" + date[:4]
        #return date[:4] + "-" + date[4:6] + "-" + date[6:8] #yyyy-mm-dd

    #hhmmss -> hh:mm AM/PM (military to regular)
    def formatTime(self, time):
        return datetime.strptime(time,'%H%M%S').strftime('%I:%M %p')
        #return time[:2] + ":" + time[2:4] + ":" + time[4:6] #hh:mm:ss
    
    #takes anonymized file, opens dicom, takes minimal info, writes png
    #adds dicom to work queue, looks up mongo record, creates and rets URL
    def processImage(self, path, dicom, ip_addr):                
        log("processing dicom")
        dicomData = pydicom.dcmread(dicom, force=True)
        if not hasattr(dicomData, 'StudyInstanceUID'):
            return retError(401, "Incorrect File Upload Type")
        dicomInfo = {'studyID' :dicomData.StudyInstanceUID, 
                        'seriesID' : dicomData.SeriesInstanceUID,
                        'siteCode' : dicomData.InstitutionName,
                        'studyDate' : self.formatDate(str(dicomData.StudyDate)),
                        'studyTime' : self.formatTime(str(dicomData.StudyTime)),
                        'SOPID' : dicomData.SOPClassUID,
                        'imgName' : str(dicom.filename)
                    }
        
        #add dicom info to db
        status, uid = self.model.createDbEntry(dicomInfo, ip_addr)
        if not status:
            return retError(500, "Failed to create database entry")

        #upload dicoms to azure
        pixel_array = self.getHounsfieldUnits(dicomData)
        status = self.model.uploadDicomToBlob(uid, dicomInfo['imgName'], pixel_array) #TODO  change key from accesscode
        if not status:
            return retError(500, "Failed to upload dicom to container")

        # log("END PROCESS SERVICE")
        return 'https://covwebapp.azurewebsites.net/fetchReport/' + uid, 201


    # using generate_container_sas
    #returns container_sas_token, account_name, container_name
    def getSasToken(self):
        return self.model.getSasToken()

    def getReportInfo(self, uid):
        log("get report info")
        info = self.model.getImageInfo(uid)
        if isinstance(info, str): #returns status if unfinished or no entry
            return info
        if(len(info['exampleImages'])):
            log("getting imageurls")
            info['imageUrls'] = []
            container_sas_token, account_name, container_name = self.getSasToken()
            for im_name in info['exampleImages']:
                info['imageUrls'].append(f"https://{account_name}.blob.core.windows.net/{container_name}/{im_name}?{container_sas_token}")
        return info

    def getExeUrl(self, exe_name):
        log("gete exe service")
        #TODO get differet Sas token
        container_sas_token, account_name, container_name = self.model.getExeSasToken()
        return f"https://{account_name}.blob.core.windows.net/{container_name}/{exe_name}?{container_sas_token}"

    #get most recent hubspot form entry and create ID from info
    #TODO just gets most recent hubspot entry. better way?
    def createUserID(self):
        return str(uuid.uuid1()) # UNTIL WE SWITCH TO HUBSPOT
        #query hub api. 
        url = f"https://api.hubapi.com/form-integrations/v1/submissions/forms/{app.config.get('HUB_FORM_ID')}?hapikey={app.config.get('HUB_API_KEY')}"
        resp = requests.get(url)
        data = json.loads(resp.text)
        subTime = data["results"][0]['submittedAt'] #most recently submitted hub form. Using submitted time as uid
        return subTime

    def saveUserID(self, ipAddr):
        userID = self.createUserID()
        self.model.saveUserID(userID, ipAddr)