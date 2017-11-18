import json
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

from multiprocessing import Process, Queue, Lock, Manager
import threading, time
import numpy as np
import facemodules_client as facemodules
import paho.mqtt.client as mqtt

Global = Manager().Namespace()

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
frameq = []
retq = []

nextprocess = 0
nextresult = 0

serverip = ""
mqttclient = None

Global.poscount = {"Left" : 0, "Right": 0, "Center": 0};

Global.training = False
Global.training_name = None

def initEngine(pronum=1, server='localhost'):
    print"initEngine"
    global serverip, processnum
    serverip = server
    processnum = pronum
    need = []
    
    for i in range(processnum):
        fq = Queue(maxsize = 1)
        rq = Queue(maxsize = 1)
        process = FaceRecognitonProcess(fq, rq, serverip)
        process.start()
        frameq.append(fq)
        retq.append(rq)
        need.append(True)

    Global.needUpdate = need
    facemodules.modules_init(serverip)

def proImageFile(imgf):
    frame = np.array(imgf)
    proCvFrame(frame)
    if Global.training:
        facemodules.training_proframe(Global.training_name, frame)
        #facemodules.training_proimage(training_name, imgf)

def proCvFrame(frame):
    global nextprocess
    fq = frameq[nextprocess]
    try:
        if (fq.full()):
            fq.get_nowait()
        fq.put((Global.training, frame, Global.needUpdate[nextprocess]))
        nextprocess = (nextprocess + 1) % processnum
    except Exception as e:
        print(e)

def trainStart(name):
    if(Global.training or Global.training_name or facemodules.training_start(name) == False):
        return False
    Global.training = True
    Global.training_name = name
    Global.poscount = {"Left" : 0, "Right": 0, "Center": 0};
    return True

def getResult():
    global nextresult
    try:
        rq = retq[nextresult]
        #rets, updated = rq.get()
        rets, updated = rq.get_nowait()
        if updated:
            need = Global.needUpdate
            need[nextresult] = False
            Global.needUpdate = need
        for i in rets:
            i["info"] = facemodules.get_info(i["name"])
        if Global.training and len(rets) == 1 and "pos" in rets[0]:
            poscnt = Global.poscount
            if poscnt[rets[0]["pos"]] < 15:
                poscnt[rets[0]["pos"]] += 1
                Global.poscount = poscnt
            if poscnt["Left"] == 15 and poscnt["Right"] == 15 and poscnt["Center"] == 15:
                facemodules.training_finish(Global.training_name)
                Global.training = False
        nextresult = (nextresult + 1) % processnum
        return rets
    except Exception as e:
        print e
        return None

def getPosCount():
    return Global.poscount["Left"], Global.poscount["Right"], Global.poscount["Center"], Global.training

deleteName = facemodules.delete_module
getNames = facemodules.get_names

def onModuleUpdated(c, d, m):
    print "get mesg"
    global processnum,callback
    need = []
    facemodules.update_modules()
    for i in range(processnum):
        need.append(True)
    Global.needUpdate = need
    if Global.training_name and facemodules.has_name(Global.training_name):
        callback(True)
        Global.training_name = None
    else:
        callback(False)

def onMqttConnect(client, userdata, flags, rc):
    print('Connected to MQTT broker with error code:' + str(rc))

def startListener(cb):
    global mqttclient, callback
    if mqttclient is not None:
        return
    mqttclient = mqtt.Client()
    mqttclient.on_message = onModuleUpdated
    mqttclient.on_connect = onMqttConnect
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

initEngine(server='ec2-52-35-84-228.us-west-2.compute.amazonaws.com')
