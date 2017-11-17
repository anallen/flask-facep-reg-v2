import json
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

from multiprocessing import Process, Queue, Lock
import threading, time
import numpy as np
import facemodules_client as facemodules
import paho.mqtt.client as mqtt


class FaceRecognitonProcess(Process):
    def __init__(self, frameq, retq, serverip):
        Process.__init__(self)
        self.frameq = frameq
        self.retq = retq
        self.serverip = serverip

    def sendResult(self, ret):
        self.retq.put(ret)

    def reciveFrame(self):
        return self.frameq.get()

    def run(self):
        import face_recg as face_recg
        
        print("recogProcess start")
        while (1):
            try:
                training, inFrame, needUpdate = self.reciveFrame()

                if (needUpdate == True):
                    face_recg.load_modules()

                if training:
                    rets = face_recg.detect_people(inFrame)
                else:
                    rets = face_recg.recog_process_frame(inFrame)
                self.sendResult((rets, needUpdate))
            except Exception as e:
                print e

processnum = 1
processes = []
frameq = []
retq = []
needUpdate = []

nextprocess = 0
nextresult = 0

serverip = ""
mqttclient = None

training = False
poscount = {"Left" : 0, "Right": 0, "Center": 0};
training_name = None

def initEngine(pronum=1, server='localhost'):
    global serverip, processnum
    serverip = server
    processnum = pronum
    
    for i in range(processnum):
        fq = Queue(maxsize = 1)
        rq = Queue(maxsize = 1)
        process = FaceRecognitonProcess(fq, rq, serverip)
        process.start()
        frameq.append(fq)
        retq.append(rq)
        processes.append(process)
        needUpdate.append(True)

    facemodules.modules_init(serverip)

def proImageFile(imgf):
    frame = np.array(imgf)
    proCvFrame(frame)
    if training:
        facemodules.training_proframe(training_name, frame)
        #facemodules.training_proimage(training_name, imgf)

def proCvFrame(frame):
    global nextprocess,training
    fq = frameq[nextprocess]
    try:
        if (fq.full()):
            fq.get_nowait()
        fq.put((training, frame, needUpdate[nextprocess]))
        nextprocess = (nextprocess + 1) % processnum
    except Exception as e:
        print(e)

def trainStart(name):
    global training,poscount,training_name
    if(training or training_name or facemodules.training_start(name) == False):
        return False
    training = True
    training_name = name
    poscount = {"Left" : 0, "Right": 0, "Center": 0};
    return True

def getResult():
    global nextresult,poscount,training,training_name
    try:
        rq = retq[nextresult]
        #rets, updated = rq.get()
        rets, updated = rq.get_nowait()
        if updated:
            needUpdate[nextresult] = False
        for i in rets:
            i["info"] = facemodules.get_info(i["name"])
        if training and len(rets) == 1 and "pos" in rets[0]:
            if poscount[rets[0]["pos"]] < 15:
                poscount[rets[0]["pos"]] += 1
            print(poscount)
            if poscount["Left"] == 15 and poscount["Right"] == 15 and poscount["Center"] == 15:
                facemodules.training_finish(training_name)
                training = False
            rets[0]["name"] = training_name + "-training"
            rets[0]['l'] = poscount["Left"]
            rets[0]['r'] = poscount["Right"]
            rets[0]['f'] = poscount["Center"]
        nextresult = (nextresult + 1) % processnum
        return rets
    except Exception as e:
        print e
        return None


deleteName = facemodules.delete_module
getNames = facemodules.get_names

def onModuleUpdated(c, d, m):
    print "get mesg"
    global processnum,callback,needUpdate,training_name
    for i in range(processnum):
        needUpdate[i] = True
    facemodules.update_modules()
    if training_name and facemodules.has_name(training_name):
        callback(True)
        training_name = None
    else:
        callback(False)

def startListener(cb):
    global mqttclient, callback
    if mqttclient is not None:
        return
    mqttclient = mqtt.Client()
    mqttclient.on_message = onModuleUpdated
    mqttclient.connect(serverip, 1883, 60)
    mqttclient.loop_start()
    mqttclient.subscribe("NXP_FACE_RECG_MODULES_UPDATED", qos=1)
    callback = cb

def stopListener():
    global mqttclient, callback
    if mqttclient is None:
        return
    mqttclient.disconnect()
    mqttclient = None
    callback = None

initEngine(server='10.193.20.77')
