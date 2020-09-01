# models- all db interactions
from . import app
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_container_sas, ContainerSasPermissions
generate_container_sas, ContainerSasPermissions
import os
import pydicom
import base64
from pymongo import MongoClient
#from . import mongo
import random
#import cv2
from skimage.io import imsave, imread
import json
import numpy as np
import math
import uuid
import logging

def log(message, type="info"):
    if type == "error":
        logging.error(message)
    else:
        #logging.info(message)
        print(message)

class CovidAppModel:
    def __init__(self):       
        self.account_name = app.config.get("AZURE_ACCT")
        self.account_key = app.config.get("AZURE_KEY")

        #get storage blob client
        #OLD jaredtutorial connect str #self.connect_str = 'DefaultEndpointsProtocol=https;AccountName=jaredtutorial9277385973;AccountKey=qgtyoU/MxAMqCMd6QbjQ7E+SMu+rqi2ynhJfcf6/rU5BdOrdlIq4j5QM6UN59vkI9wLEL7tAkQ1LDCW4mL6L+A==;EndpointSuffix=core.windows.net'
        self.blob_service_client = BlobServiceClient.from_connection_string(app.config.get("AZURE_CON_STR") )
        self.container_name = 'webappimgs'

        self.mongoClient = MongoClient(app.config.get("MONGO_STR"))
        self.studies_coll = self.mongoClient.db.studies

    def getSasToken(self):
        container_sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            account_key=self.account_key,
            permission=ContainerSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        return container_sas_token, self.account_name, self.container_name

    def getExeSasToken(self):
        container_name = "exe"
        container_sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=container_name,
            account_key=self.account_key,
            permission=ContainerSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=2)
        )
        return container_sas_token, self.account_name, container_name
    
    def saveUserID(self, userID, ipAddr):
        coll = self.mongoClient.db.installer_access
        data = {'userID': userID,
                'ip_address': ipAddr,
                'lastAccessed': datetime.utcnow()}
        #check if ip_addr already added
        entry = coll.find_one({'ip_address': ipAddr})
        if(entry):
            coll.update({'ip_address': ipAddr}, data)
        else: #adds to existing userID entry if exists, else inserts new
            coll.update({'userID': userID}, data, upsert=True)
        return

    def createDbEntry(self, dicomInfo, ipAddr):
        #check for study & series ID (id)
        entry = self.studies_coll.find_one({'studyID': dicomInfo['studyID']})
        if(entry):
            uid = entry['uid']
            query = {'studyID': dicomInfo['studyID']}
            data = {
                'SOPID' : dicomInfo['SOPID'], #TODO this should be array. Needed tho??
                'lastUpdated' : datetime.utcnow(),
                'imCount': entry['imCount'] + 1,
                'createdTime' : datetime.utcnow(),
                'ipAddress': ipAddr
            }
            status = self.studies_coll.find_one_and_update(query, {'$set': data})
        else:
            #create new accesscode
            codeLen = 8 #0 pad to always be 8 chars
            accessCode = str(int(dicomInfo['studyID'][-3:]) * int(dicomInfo['seriesID'][-3:]) * 23).zfill(codeLen)
            uid = str(uuid.uuid1())
            #add study instance UID, site code, series UID, SOP UID(?), count of imgs(?), last updated time
            data = {'studyID': dicomInfo['studyID'], 
                    'seriesID' : dicomInfo['seriesID'],
                    'siteCode' : dicomInfo['siteCode'],
                    'uid' : uid,
                    'studyDate' : dicomInfo['studyDate'],
                    'studyTime' : dicomInfo['studyTime'],
                    'SOPID' : dicomInfo['SOPID'],
                    'lastUpdated' : datetime.utcnow(),
                    'imCount': 1,
                    'numProcessed' : 0,
                    'accessCode' : accessCode,
                    'topImages': [{"pred": 0, "im":""},{"pred": 0, "im":""},{"pred": 0, "im":""}],
                    'ipAddress': ipAddr
            }
            status = self.studies_coll.insert_one(data)
        #TODO: check it worked and return status
        status = True
        return status, uid

    def uploadDicomToBlob(self, key, filename, dicom):        
        #TODO thread this function
        #write array to png
        filename = filename
        if filename.find('.dcm') != -1:
            filename = filename.replace('.dcm','.png')
        elif (filename.find('.raw') != -1):
            filename = filename.replace('.raw','.png')
        else :
            filename + ".png"

        dicom = np.array(dicom)
        dicom += 2000
        dicom *= 10
        imsave(filename, dicom.astype(np.uint16))
        dcmFile = open(filename, "rb")

        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=key + '/' + filename) #key/txdDoc.txt
        blob_client.upload_blob(dcmFile, overwrite=True) 

        dcmFile.close()

        #delete local file
        os.remove(filename)

        #TODO: if error return False
        return True

    def getTrainingInfo(self):
        #query db for trianing info
        info = self.mongoClient.db.model_info.find_one({'name': 'modelInfo'})
        if info: 
            return info
        else: 
            return False

    def getImageInfo(self, uid):
        log("getting img info", uid)
        entry = self.studies_coll.find_one({'uid': uid})

        #if not valid study 
        #TODO check that there are images- not just no db entry
        if not entry:
            logging.error("No study in db")
            return "EXPIRED"

        #don't bother getting preds if we don't have many images
        secsSinceUpd = (datetime.utcnow() - entry['lastUpdated']).total_seconds()
        minsSinceUpd = divmod(secsSinceUpd, 60)[0] 
        #If we have less than 15 imgs and it's been less than 30 mins we'll assume we don't have all the data
        if entry['numProcessed'] < 15 and minsSinceUpd < 30: 
            return "UNFINISHED"

        preds = self.getPreds(entry['uid'])
        overall, covCount, conf = self.getOverallPred(preds)

        exImages = []
        if "topImages" in entry:
            exImages = [i.get("im") for i in entry['topImages']]

        trainInfo = self.getTrainingInfo()

        ret = {'facility': entry['siteCode'],
                'numImgs' : entry['imCount'],
                'numProcessed' : entry['numProcessed'],
                'studyDate': entry['studyDate'],
                'studyTime' : entry['studyTime'],
                'accessCode': entry['accessCode'],
                'exampleImages': exImages,
                'overall' : overall,
                'pred': str(conf) + "%", #TODO change back to numProcessed!
                'percShown': str(math.floor(covCount/entry['numProcessed'] * 10)) + "%",
                'numModels' : trainInfo['numModels'],
                'numTrainScans' : trainInfo['numTrainScans'],
                'numTrainImages' : trainInfo['numTrainImages'],
                'specificity' : trainInfo['specificity'],
                'sensitivity' : trainInfo['sensitivity'],
                'accuracy' : trainInfo['accuracy'],
                'currentTime' : datetime.now().strftime("%m/%d/%Y %H:%M")
         }
        
        return ret

    #Calcs and rets overall covid prediction and confidance level
    def getOverallPred(self, data):
        indetCutoff = 0.4
        yesCutoff = 0.55
        
        maxpred = max(data[:,-1])
        outp = "NO"
        if maxpred >= indetCutoff:
            outp="INDETERMINATE"
        if maxpred > yesCutoff:
            outp="YES"

        #conf level is y on logarithmic curve fit to test data
        infpt = 0.5313
        hillcoef = -24.7729
        conf = round(1/(1+((maxpred/infpt)**hillcoef)), 3)
        if maxpred < indetCutoff:
            conf = 1 - conf
        conf *= 100

        covCount = 0
        ar = np.array(data)
        #Get count of ims pred >= 0.4
        colct = np.array([len(np.where(row >= indetCutoff)[0]) for row in ar])
        covCount = len(colct)

        return outp, covCount, conf

    #uses accessCode to get azure blob with predictions and return numpy array of preds (unsorted)
    def getPreds(self, accessCode):
        #download txt prediction file from azure
        filename = accessCode + '-results.txt'
        blobname = accessCode + "/" + accessCode + '-results.txt'
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blobname)
        downFile = open(filename, "wb+")
        downFile.write(blob_client.download_blob().readall())
        downFile.close()

        #read txt file to numpy array TODO make this faster- np.loadtxt()
        txtfile = open(filename, "r")
        line = txtfile.readline().strip()
        cnt = 1
        ary = []
        while line:
            # im_name = line.split(":")[0][0:3] #read im_name as number
            outp = line.split(":")[-1][:-1].split(',')
            # outp.insert(0,im_name) #app im_names as col 0
            if(len(outp) == 5): #ignore weird empty lines
                fl_outp = [float(i) for i in outp] 
                ary.append(fl_outp)
            line = txtfile.readline().strip()
            cnt += 1 
        txtfile.close()

        os.remove(filename)
        return np.array(ary)
