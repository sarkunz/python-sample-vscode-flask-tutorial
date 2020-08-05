# models- all db interactions
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

class CovidAppModel:
    def __init__(self):       
        self.account_name = 'storageaccountdevus81b4'
        self.account_key = 'wqhKaJKWMItAW3EnCj9fN4RWD2VzpLAw1yykhvS2e2uvWrYOez1bXMsLizgPQRbmaYOEo+0oQtIlaDW2wuer9A=='

        #get storage blob client
        #OLD jaredtutorial connect str #self.connect_str = 'DefaultEndpointsProtocol=https;AccountName=jaredtutorial9277385973;AccountKey=qgtyoU/MxAMqCMd6QbjQ7E+SMu+rqi2ynhJfcf6/rU5BdOrdlIq4j5QM6UN59vkI9wLEL7tAkQ1LDCW4mL6L+A==;EndpointSuffix=core.windows.net'
        connect_str = 'DefaultEndpointsProtocol=https;AccountName=storageaccountdevus81b4;AccountKey=wqhKaJKWMItAW3EnCj9fN4RWD2VzpLAw1yykhvS2e2uvWrYOez1bXMsLizgPQRbmaYOEo+0oQtIlaDW2wuer9A==;EndpointSuffix=core.windows.net'
        self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        self.container_name = 'webappimgs'

        self.mongoCli = MongoClient('mongodb+srv://skunzler:sarah96@cluster0.22wsg.azure.mongodb.net/<dbname>?retryWrites=true&w=majority')

    def getSasToken(self):
        container_sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            account_key=self.account_key,
            permission=ContainerSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        return container_sas_token, self.account_name, self.container_name

    def createDbEntry(self, dicomInfo):
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
                'studyTime' : dicomInfo['studyTime'],
                'SOPID' : dicomInfo['SOPID'], #TODO this should be array. Needed tho??
                'lastUpdated' : datetime.now(),
                'imCount': imCount + 1,
                'accessCode' : accessCode,
            }
        query = {'studyID': dicomInfo['studyID']}
        status = studies_coll.update(query, data, upsert=(not entry))
        #TODO: check it worked and return status
        print("STATUS DB", status)
        status = True
        return status, accessCode

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
        exImages = entry['exampleImages'] if "exampleImages" in entry else []
        print("example images", exImages)
        
        ret = {'facility': entry['siteCode'],
                'numImgs' : entry['imCount'],
                'studyDate': entry['studyDate'],
                'studyTime' : entry['studyTime'],
                'accessCode': entry['accessCode'],
                'exampleImages': exImages,
                'overall' : overall,
                'pred': '91%',
                'percShown': '5%',
                'recommendation' : "It's recommended you do additional clinical testing as per current guidelines and quarentine.",
                'availUntil' : '08/12/2020' #TODO how are we going to delete these?
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
