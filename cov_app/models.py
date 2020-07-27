# models- all db interactions
import datetime
#from azure.storage.queue import QueueService
from azure.storage.blob import BlockBlobService, PublicAccess #BlobServiceClient, BlobClient, ContainerClient,
import os
import pydicom
import base64
from pymongo import MongoClient
#from . import mongo
import random

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
        #connect_str = 'DefaultEndpointsProtocol=https;AccountName=jaredtutorial9277385973;AccountKey=qgtyoU/MxAMqCMd6QbjQ7E+SMu+rqi2ynhJfcf6/rU5BdOrdlIq4j5QM6UN59vkI9wLEL7tAkQ1LDCW4mL6L+A==;EndpointSuffix=core.windows.net'
        #self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        self.container_name = 'webappimgs'
        self.block_blob_service = BlockBlobService(account_name=account_name, account_key=account_key)

        self.mongoCli = MongoClient('mongodb+srv://skunzler:sarah96@cluster0.22wsg.azure.mongodb.net/<dbname>?retryWrites=true&w=majority')

    def createDbEntry(self, dicomInfo):
        logger.info("MODEL CREATE DB ENTRY")
        studies_coll = self.mongoCli.db.studies
        #check for study & series ID (id)
        #if not created, add it
            #studyID as key
        #CREATE and SET random access code
        accessCode = dicomInfo['studyID'][0:2] + dicomInfo['seriesID'][0:2] + str(random.randint(10, 99))
        #SET study instance UID, site code, series UID, SOP UID(?), count of imgs(?), last updated time
        query = {'studyID': dicomInfo['studyID']}
        data = {'studyID': dicomInfo['studyID'], 
                    'seriesID' : dicomInfo['seriesID'],
                    'siteCode' : dicomInfo['siteCode'],
                    'SOPID' : dicomInfo['SOPID'],
                    'imgCount' : dicomInfo['imgCount'],
                    'lastUpdated' : datetime.datetime.now(),
                    'accessCode' : accessCode
                }
        status = studies_coll.update(query, data, upsert=True)
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

    def uploadDicomToBlob(self, key, dicomPath):        
        #TODO do this in a thread
        test_list = [ f for f in os.listdir(dicomPath)]
        for f in test_list[:5]:   # remove "[:10]" to upload all images
            self.block_blob_service.create_blob_from_path(self.container_name,(key + '/' + f),os.path.join(dicomPath,f))
            print("UPLOAD PATH:", os.path.join(dicomPath,f))
        #TODO: if error return False
        return True

    def getImageInfo(self, params):
        #facility, studydate, studytime, pred(iction), percShown, overall, runIndxs, photos, recommendation
        return {"facility": "someFacility",
            "studyTime": datetime.datetime.now()}

    def get(self, params):
        return -1

#get info for study

#add dicom img to db
