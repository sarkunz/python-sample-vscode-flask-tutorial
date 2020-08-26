# services- business logic of API
import datetime
import pydicom
import os
from .models import CovidAppModel
import numpy as np
import logging
import time
import uuid

def log(message, type="info"):
    if type == "error":
        logging.error(message)
    else:
        #logging.info(message)
        print(message)

def retError(code, message):
    log(message)
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

    #yyyymmdd -> yyyy-mm-dd
    def formatDate(self, date):
        return date[:4] + "-" + date[4:6] + "-" + date[6:8]

    #hhmmss -> hh:mm:ss
    def formatTime(self, time):
        return time[:2] + ":" + time[2:4] + ":" + time[4:6]
    
    #takes anonymized file, opens dicom, takes minimal info, writes png
    #adds dicom to work queue, looks up mongo record, creates and rets URL
    def processImage(self, path, dicom, ip_addr):                
        log("processing dicom")
        st = time.time()
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
        log("processed")
        
        #add dicom info to db
        status, uid = self.model.createDbEntry(dicomInfo, ip_addr)
        if not status:
            return retError(500, "Failed to create database entry")

        #upload dicoms to azure
        pixel_array = self.getHounsfieldUnits(dicomData)
        logging.info("ACTUAL processing time " +  str(time.time() - st))
        stup = time.time()
        status = self.model.uploadDicomToBlob(uid, dicomInfo['imgName'], pixel_array) #TODO  change key from accesscode
        if not status:
            return retError(500, "Failed to upload Dicom to Blob")
        logging.info("END UP " + str(time.time() - stup))

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
    #TODO START HERE
    def createUserID(self):
        #QUERY hub api. 
        url = f"https://api.hubapi.com/form-integrations/v1/submissions/forms/{app.config.get('HUB_FORM_ID')}?hapikey={app.config.get('HUB_API_KEY')}"
        #Use submittedAt value for UID
        #id = resp[0].submittedAt
        id = "userID"
        #for ids, get most recent id not in db
        return id

    def saveUserID(self, ipAddr):
        userID = str(uuid.uuid1()) #self.createUserID()
        self.model.saveUserID(userID, ipAddr)