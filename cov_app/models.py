# models- all db interactions
import datetime
#from azure.storage.queue import QueueService
#from azure.storage.blob import BlockBlobService, PublicAcces
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

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

import logging
logger = logging.getLogger(__name__)

class CovidAppModel:
    def __init__(self):
        #connect to 
        
        #get queue
        account_name = 'jaredtutorial9277385973'
        account_key = 'qgtyoU/MxAMqCMd6QbjQ7E+SMu+rqi2ynhJfcf6/rU5BdOrdlIq4j5QM6UN59vkI9wLEL7tAkQ1LDCW4mL6L+A=='
        # self.queue = QueueService(account_name=account_name, account_key=account_key)
        # self.queue_name = "covidqueue"

        #get storage blob client
        connect_str = 'DefaultEndpointsProtocol=https;AccountName=jaredtutorial9277385973;AccountKey=qgtyoU/MxAMqCMd6QbjQ7E+SMu+rqi2ynhJfcf6/rU5BdOrdlIq4j5QM6UN59vkI9wLEL7tAkQ1LDCW4mL6L+A==;EndpointSuffix=core.windows.net'
        self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        self.container_name = 'webappimgs'
        #self.block_blob_service = BlockBlobService(account_name=account_name, account_key=account_key)

        self.mongoCli = MongoClient('mongodb+srv://skunzler:sarah96@cluster0.22wsg.azure.mongodb.net/<dbname>?retryWrites=true&w=majority')

    def createDbEntry(self, dicomInfo):
        logger.info("MODEL CREATE DB ENTRY")
        studies_coll = self.mongoCli.db.studies
        #check for study & series ID (id)
        entry = studies_coll.find_one({'studyID': dicomInfo['studyID']})
        if(entry):
            accessCode = entry['accessCode']
            imCount = entry['imCount']
        else:
            imCount = 0
            #create new accesscode
            accessCode = dicomInfo['studyID'][-3:] + dicomInfo['seriesID'][-3:] + str(random.randint(1000, 9999)) #TODO only if this hasn't been set before
        #add study instance UID, site code, series UID, SOP UID(?), count of imgs(?), last updated time
        data = {'studyID': dicomInfo['studyID'], 
                    'seriesID' : dicomInfo['seriesID'],
                    'siteCode' : dicomInfo['siteCode'],
                    'studyDate' : dicomInfo['studyDate'],
                    'SOPID' : dicomInfo['SOPID'],
                    'lastUpdated' : datetime.datetime.now(),
                    'imCount': imCount + 1,
                    'accessCode' : accessCode,
                }
        query = {'studyID': dicomInfo['studyID']}
        imgData = { 
                    '$push': {
                        "imgNames": dicomInfo['imgName']
                    }
                }
        status = studies_coll.update(query, data, upsert=True)
        status = studies_coll.update(query, imgData) #TODO combine into one update. Not totally working
        #TODO: check it worked and return status
        print("STATUS DB", status)
        status = True
        return status, accessCode
    
    def addToQueue(self, message):
        pass
        # message_bytes = message.encode('ascii')
        # base64_bytes = base64.b64encode(message_bytes)
        # print("64 TYPE: ", base64_bytes.dtype)
        # self.queue.put_message(self.queue_name, base64_bytes)
        # #base64_message = base64_bytes.decode('ascii')

    def uploadDicomToBlob(self, key, filename, dicom):        
        #TODO do this in a thread
        print("UPLOADING TO ", (key + '/' + filename))
        
        #write array to png
        filename = filename.replace('.dcm','.png')
        dicom = np.array(dicom)
        dicom += 2000
        dicom *= 10
        imsave(filename, dicom.astype(np.uint16))
        #cv2.imwrite(filename,dicom.astype(np.uint16))
        dcmFile = open(filename, "rb")
        print("wrote to png")

        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=key + '/' + filename) #key/txdDoc.txt
        blob_client.upload_blob(dcmFile, overwrite=True) 

        dcmFile.close()

        #delete local file
        os.remove(filename)

        print("UPLOADED @:", key + '/' + filename)
        #TODO: if error return False
        return True

    def getImageInfo(self, studyID):
        #facility, studydate, studytime, pred(iction), percShown, overall, runIndxs, photos, recommendation
        print("getting img info")
        studies_coll = self.mongoCli.db.studies
        entry = studies_coll.find_one({'studyID': studyID})
        preds = self.getPreds(entry['accessCode'])
        overall = self.getOverallPred(preds)

        ret = {'facility': entry['siteCode'],
                'numImgs' : entry['imCount'],
                'studyDate': entry['studyDate'],#entry.studyDate,
                'accessCode': entry['accessCode'],
                'overall' : overall,
                'pred': '91%',
                'percShown': '5%',
                'recommendation' : "It's recommended you do additional clinical testing as per current guidelines and quarentine.",
                'availUntil' : '08/06/2020'
         }# studytime, pred(iction), percShown, overall, runIndxs, photos, recommendation

        return ret

    def getOverallPred(self, data):
        mean = np.mean(data)
        outp = "NO"
        tr = np.array(data) #.transpose()
        ####indet
        #if norm area > 0.45
        if mean > 0.45:
            outp = "INDETERMINATE"
        
        #if 2+ models pred 0.75+ on 3+ imgs
        colct = np.array([len(np.where(row > 0.75)[0]) for row in tr])
        rowct = len(colct[colct >= 2])
        if(rowct >= 3):
            outp = "INDETERMINATE"

        ######yes
        #if norm area > 0.65
        if mean > 0.65:
            outp = "YES"

        #if 2+ models pred 0.90+ on 2+ imgs
        colct = np.array([len(np.where(row > 0.90)[0]) for row in tr])
        rowct = len(colct[colct >= 2])
        if(rowct >= 2):
            outp = "YES"

        # #if 2+ models pred 0.98+ on 2+ imgs
        # colct = np.array([len(np.where(row > 0.98)[0]) for row in tr])
        # rowct = len(colct[colct >= 2])
        # if(rowct >= 2):
        #     outp = "yes"

        ###else outp is no
        return outp

    #uses accessCode to get azure blob with predictions and return numpy array of preds (unsorted)
    def getPreds(self, accessCode):
        #download txt prediction file from azure
        filename = accessCode + '-results.txt'
        blobname = accessCode + "/" + accessCode + '-results.txt'
        print("getting blob ", blobname)
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

    def get(self, params):
        return -1

#get info for study

#add dicom img to db
