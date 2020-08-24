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
        log("get exe sas model")
        container_name = "exe"
        container_sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=container_name,
            account_key=self.account_key,
            permission=ContainerSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=2)
        )
        return container_sas_token, self.account_name, container_name
    
    def saveUserID(self, userID, facility):
        log("save userID")
        coll = self.mongoClient.db.installer_access
        coll.update({'hubUserID': userID}, {'hubUserID': userID, 'facility': facility}, upsert=True)

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
            #TODO always 8 chars- zero pad
            accessCode = str(int(dicomInfo['studyID'][-3:]) * int(dicomInfo['seriesID'][-3:]) * 23)# str(random.randint(1000, 9999)) #TODO only if this hasn't been set before
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
        log("STATUS DB", status)
        status = True
        return status, uid

    def uploadDicomToBlob(self, key, filename, dicom):        
        #TODO do this in a thread
        log("UPLOADING TO ", (key + '/' + filename))
        
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
        #cv2.imwrite(filename,dicom.astype(np.uint16))
        dcmFile = open(filename, "rb")

        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=key + '/' + filename) #key/txdDoc.txt
        blob_client.upload_blob(dcmFile, overwrite=True) 

        dcmFile.close()

        #delete local file
        os.remove(filename)

        log("UPLOADED @:", key + '/' + filename)
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
        secsSinceUpd = (entry['lastUpdated'] - datetime.utcnow()).total_seconds()
        minsSinceUpd = divmod(secsSinceUpd, 60)[0] 
        print("numprocessed", entry['numProcessed'])
        log("MINSSINCEUPD" +  str(minsSinceUpd))
        #If we have less than 15 imgs and it's been less than 30 mins we'll assume we don't have all the data
        # if entry['numProcessed'] < 15 and minsSinceUpd < 30: 
        #     return "UNFINISHED"

        preds = self.getPreds(entry['uid'])
        overall, covCount, conf = self.getOverallPred(preds)

        exImages = []
        if "topImages" in entry:
            exImages = [i.get("im") for i in entry['topImages']]
        log("topimages", exImages)     

        trainInfo = self.getTrainingInfo()

        ret = {'facility': entry['siteCode'],
                'numImgs' : entry['imCount'],
                'numProcessed' : entry['numProcessed'],
                'studyDate': entry['studyDate'],
                'studyTime' : entry['studyTime'],
                'accessCode': entry['accessCode'],
                'exampleImages': exImages,
                'overall' : overall,
                'pred': conf, #TODO change back to numProcessed!
                'percShown': str(math.floor(covCount/entry['imCount'] * 10)) + "%", #str(math.floor(covCount/entry['numProcessed'] * 10)) + "%",
                'recommendation' : "It's recommended you do additional clinical testing as per current guidelines and quarentine.",
                'numModels' : trainInfo['numModels'],
                'numTrainScans' : trainInfo['numTrainScans'],
                'numTrainImages' : trainInfo['numTrainImages'],
                'specificity' : trainInfo['specificity'],
                'sensitivity' : trainInfo['sensitivity'],
                'accuracy' : trainInfo['accuracy'],
                'currentTime' : datetime.now().strftime("%m/%d/%Y %H:%M")
         }
        
        return ret

    def getOverallPred(self, data):
        mean = np.mean(data)
        outp = "NO"
        conf = "50%"
        covCount = 0
        tr = np.array(data) #.transpose()
        ####indet
        #if norm area > 0.45
        if mean > 0.35:
            outp = "INDETERMINATE"
        
        #if 2+ models pred 0.75+ on 2+ imgs
        colct = np.array([len(np.where(row > 0.75)[0]) for row in tr])
        rowct = len(colct[colct >= 2])
        if(rowct >= 2):
            outp = "INDETERMINATE"
            covCount = rowct

        ######yes
        #if norm area > 0.65
        if mean > 0.55:
            outp = "YES"
            conf = "95%"

        #if 2+ models pred 0.90+ on 2+ imgs
        colct = np.array([len(np.where(row > 0.90)[0]) for row in tr])
        rowct = len(colct[colct >= 2])
        if(rowct >= 2):
            outp = "YES"
            conf = "95%"

        # #if 2+ models pred 0.98+ on 2+ imgs
        # colct = np.array([len(np.where(row > 0.98)[0]) for row in tr])
        # rowct = len(colct[colct >= 2])
        # if(rowct >= 2):
        #     outp = "yes"

        ###else outp is no
        return outp, covCount, conf

    #uses accessCode to get azure blob with predictions and return numpy array of preds (unsorted)
    def getPreds(self, accessCode):
        #download txt prediction file from azure
        filename = accessCode + '-results.txt'
        blobname = accessCode + "/" + accessCode + '-results.txt'
        log("getting blob ", blobname)
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
