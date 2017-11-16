import json
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

from multiprocessing import Process, Queue, Lock
import threading, time
import numpy as np


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
#        face_recg.recog_engine_init(serverip=self.serverip)
        
        print("recogProcess start")
        face_recg.load_modules()
        while (1):
            try:
                recognition, inFrame, needUpdate = self.reciveFrame()

#                if (needUpdate == 1)

                if recognition:
                    rets = face_recg.recog_process_frame(inFrame)
                else:
                    rets = face_recg.detect_people(inFrame)
                self.sendResult((rets, needUpdate))
            except Exception as e:
                print e


class FaceRecogniton():
    def __init__(self, processnum=1, serverip='localhost'):
        self.processes = []
        self.frameq = []
        self.retq = []
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

    def setRetCallback(self, callback):
        if self.retCallback is not None:
            return
        self.t = threading.Thread(target=self.getResult)
        self.retCallback = callback
        self.t.start()

    def proImageFile(self, imgf, recognition=True):
        frame = np.array(imgf)
        self.proCvFrame(frame, recognition)

    def proCvFrame(self, frame, recognition=True):
        frameq = self.frameq[self.nextprocess]
        try:
            if (frameq.full()):
                frameq.get_nowait()
            frameq.put((recognition, frame, 1))
            self.nextprocess = (self.nextprocess + 1) % self.processnum
        except Exception as e:
            print(e)

    def getResult(self):
       try:
           retq = self.retq[self.nextresult]
           ret, updated = retq.get_nowait()
           self.nextresult = (self.nextresult + 1) % self.processnum
           return ret
       except Exception as e:
           return None



facerecg = FaceRecogniton(processnum=1)

