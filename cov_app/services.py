# services- business logic of API
import datetime
import pydicom
import os
from .models import CovidAppModel
import socket

import logging
logger = logging.getLogger(__name__)

class CovidAppServices:
    def __init__(self):
        self.model = CovidAppModel()
    
    def create(self, params):
        self.model.create(params)
    
    #takes anonymized file, opens dicom, takes minimal info
    #adds dicom to work queue, looks up mongo record, creates and rets URL
    def processImage(self, path, dicom):
        logger.info("START PROCESS IMAGE SERVICE")
        
        outp = "static\\images\\pngs\\"
        outdir = os.path.join(path, outp)
        
        print("processing dicom")
        dicomData = pydicom.dcmread(dicom, force=True)
        dicomInfo = {'studyID' :dicomData.StudyInstanceUID, 
                        'seriesID' : dicomData.SeriesInstanceUID,
                        'siteCode' : 'UI-RAI', #TODO how are we getting this?
                        'studyDate' : dicomData.StudyDate,
                        'SOPID' : dicomData.SOPClassUID,
                        'imgName' : str(dicom.filename)
                    }
        
        #add dicom info to db
        status, accessCode = self.model.createDbEntry(dicomInfo)
        if not status:
            resp = "Failed to create DB entry."
            return resp

        #TODO thread this
        #upload dicoms to azure
        status = self.model.uploadDicomToBlob(accessCode, dicomInfo['imgName'], dicomData.pixel_array) #TODO  change key from accesscode
        if not status:
            resp = "Failed to upload Dicom to Blob"
            return resp

        #FOR NOW USING STUDY ID- TODO CONVERT TO HASHMAP
        resp = dicomInfo['studyID'] #accessCode + " " + dicomInfo['studyID'] + "/" + dicomInfo['seriesID']

        # print("END PROCESS SERVICE")
        hostname = socket.gethostname()    
        IPAddr = socket.gethostbyname(hostname)  
        return 'http://' + str(IPAddr) + ':5000/fetchReport/' + resp

    def isValidToken(self, token):
        #check for token in DB
        return True

    def getReportInfo(self, studyID):
        info = self.model.getImageInfo(studyID)
        return info
