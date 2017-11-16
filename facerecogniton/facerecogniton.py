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
#            try:
                recognition, inFrame, needUpdate = self.reciveFrame()

                if (needUpdate == True):
                    face_recg.load_modules()

                if recognition:
                    rets = face_recg.recog_process_frame(inFrame)
                else:
                    rets = face_recg.detect_people(inFrame)
                self.sendResult((rets, needUpdate))
#            except Exception as e:
#                print e


class FaceRecogniton():
    def __init__(self, processnum=1, serverip='localhost'):
        self.processes = []
        self.frameq = []
        self.retq = []
        self.needUpdate = []
        self.serverip = serverip
        self.nextprocess = 0
        self.nextresult = 0
        self.processnum = processnum

        for i in range(processnum):
            frameq = Queue(maxsize = 1)
            retq = Queue(maxsize = 1)
            process = FaceRecognitonProcess(frameq, retq, serverip)
            process.start()
            self.frameq.append(frameq)
            self.retq.append(retq)
            self.processes.append(process)
            self.needUpdate.append(True)

        facemodules.modules_init(self.serverip)
        self.mqttclient = None

    def proImageFile(self, imgf, recognition=True):
        frame = np.array(imgf)
        self.proCvFrame(frame, recognition)

    def proCvFrame(self, frame, recognition=True):
        frameq = self.frameq[self.nextprocess]
        try:
            if (frameq.full()):
                frameq.get_nowait()
            frameq.put((recognition, frame, self.needUpdate[self.nextprocess]))
            self.nextprocess = (self.nextprocess + 1) % self.processnum
        except Exception as e:
            print(e)

    def getResult(self):
       try:
           retq = self.retq[self.nextresult]
           ret, updated = retq.get_nowait()
           if updated == True:
               self.needUpdate[self.nextresult] = False
           self.nextresult = (self.nextresult + 1) % self.processnum
           return ret
       except Exception as e:
           return None

    def deleteName(self, name):
        return facemodules.delete_module(name)

    def getNames(self):
        return facemodules.get_names()

    def onModuleUpdated(self, c, d, m):
        print "get mesg"
        for i in range(self.processnum):
            self.needUpdate[i] = False
        facemodules.update_modules()
        self.callback()

    def startListener(self, callback):
        if self.mqttclient is not None:
            return
        self.mqttclient = mqtt.Client()
        self.mqttclient.on_message = self.onModuleUpdated
        self.mqttclient.on_connect = self.__onMqttConnect
        self.mqttclient.connect(self.serverip, 1883, 60)
        self.mqttclient.loop_start()
        self.mqttclient.subscribe("NXP_FACE_RECG_MODULES_UPDATED", qos=1)
        self.callback = callback
    def __onMqttConnect(self, client, userdata, flags, rc):
        print('Connected to MQTT broker with error code:' + str(rc))





