# services- business logic of API
import datetime
import pydicom
import os
from .models import CovidAppModel

import logging
logger = logging.getLogger(__name__)

class CovidAppServices:
    def __init__(self):
        self.model = CovidAppModel()
    
    def create(self, params):
        self.model.create(params)

    def getHounsfieldUnits(self, dicom):
        data = dicom.pixel_array
        correctedSlope = 1 if dicom.RescaleSlope < 1 else dicom.RescaleSlope
        #correctedSlope = 1 if (dicom.RescaleSlope == 0) else dicom.RescaleSlope
        data = (data * correctedSlope) + dicom.RescaleIntercept
        data = np.clip(data,a_min=-2000,a_max=None)
        return data
    
    #takes anonymized file, opens dicom, takes minimal info, writes png
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
        pixel_array = self.getHounsfieldUnits(dicomData)
        status = self.model.uploadDicomToBlob(accessCode, dicomInfo['imgName'], pixel_array) #TODO  change key from accesscode
        if not status:
            resp = "Failed to upload Dicom to Blob"
            return resp

        #FOR NOW USING STUDY ID- TODO CONVERT TO HASHMAP
        resp = dicomInfo['studyID'] #accessCode + " " + dicomInfo['studyID'] + "/" + dicomInfo['seriesID']

        # print("END PROCESS SERVICE")
        return 'http://covwebapp.azurewebsites.net/fetchReport/' + resp

    def isValidToken(self, token):
        #check for token in DB
        return True

    def getReportInfo(self, studyID):
        info = self.model.getImageInfo(studyID)
        return info
