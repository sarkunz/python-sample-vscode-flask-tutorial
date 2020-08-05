# services- business logic of API
import datetime
import pydicom
import os
from .models import CovidAppModel
import numpy as np

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

    #yyyymmdd -> yyyy-mm-dd
    def formatDate(self, date):
        return date[:4] + "-" + date[4:6] + "-" + date[6:8]

    #hhmmss -> hh:mm:ss
    def formatTime(self, time):
        return time[:2] + ":" + time[2:4] + ":" + time[4:6]
    
    #takes anonymized file, opens dicom, takes minimal info, writes png
    #adds dicom to work queue, looks up mongo record, creates and rets URL
    def processImage(self, path, dicom):                
        print("processing dicom")
        dicomData = pydicom.dcmread(dicom, force=True)
        dicomInfo = {'studyID' :dicomData.StudyInstanceUID, 
                        'seriesID' : dicomData.SeriesInstanceUID,
                        'siteCode' : dicomData.InstitutionName, #TODO how are we getting this?
                        'studyDate' : self.formatDate(str(dicomData.StudyDate)),
                        'studyTime' : self.formatTime(str(dicomData.StudyTime)),
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
        return 'https://covwebapp.azurewebsites.net/fetchReport/' + resp


    # using generate_container_sas
    #returns container_sas_token, account_name, container_name
    def getSasToken(self):
        return self.model.getSasToken()

    def getReportInfo(self, studyID):
        print("get report info")
        info = self.model.getImageInfo(studyID)
        if(info == -1):
            return -1
        if(len(info['exampleImages'])):
            print("getting imageurls")
            info['imageUrls'] = []
            container_sas_token, account_name, container_name = self.getSasToken()
            for im_name in info['exampleImages']:
                info['imageUrls'].append(f"https://{account_name}.blob.core.windows.net/{container_name}/{im_name}?{container_sas_token}")
        return info
