# services- business logic of API
import datetime
import pydicom
#import cv2
import os
from .models import CovidAppModel

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
        #open dicom, get infoseries-000001/	
        inp = "static\\images\\series-000001\\"
        outp = "static\\images\\pngs\\"
        inputdir = os.path.join(path, inp)
        outdir = os.path.join(path, outp)

        dicomInfo = {'studyID' : 'STUDYID',
                        'seriesID' : 'SERIESID',
                        'siteCode' : 'SITECODE',
                        'SOPID' : 'SOPID',
                        'imgCount' : 1
                    }
        resp = "made it here"
        # data = pydicom.read_file(inputdir)
        # for key in data.dir():
        #     value = getattr(data, key, '')
        #     dicomInfo[key] = value

        #add dicom info to db
        # status, accessCode = self.model.createDbEntry(dicomInfo)
        # if not status:
        #     resp = "Failed to create DB entry."
        #     return resp

        # #upload dicoms to azure
        # status = self.model.uploadDicomToBlob(accessCode, inputdir)
        # if not status:
        #     resp = "Failed to upload Dicom to Blob"
        #     return resp

        # resp = accessCode

        # #convert to png --move to queue
        # #test_list = [ f for f in  os.listdir(inputdir)]
        # # for f in test_list[:10]:   # remove "[:10]" to convert all images 
        # #     ds = pydicom.read_file(inputdir + f) # read dicom image
        # #     print(inputdir + f)
        # #     img = ds.pixel_array # get image array
        # #     print(img.dtype)
        # #     cv2.imwrite(outdir + f.replace('.dcm','.png'),img) # write png image

        # print("END PROCESS SERVICE")
        return resp

    def isValidToken(self, token):
        #check for token in DB
        return True

    def getReportInfo(self, accessCode):
        info = self.model.getImageInfo(params=accessCode)
        return info
