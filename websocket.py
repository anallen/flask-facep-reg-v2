import json
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS
from twisted.internet import task, defer

from twisted.internet.ssl import DefaultOpenSSLContextFactory
import facerecogniton.facerecogniton as facerecg
from multiprocessing import Process
import time, StringIO, base64, os
from PIL import Image
import threading

video_device = ""
 
class FaceServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        super(FaceServerProtocol, self).__init__()
        self.new_person = None

    def modulesUpdate(self, finish=False):
        names = facerecg.getNames()
        self.sendSocketMessage("LOADNAME_RESP", ",".join(names))
        if finish:
            self.sendSocketMessage("TRAINFINISH_RESP")
            
    def onOpen(self):
        facerecg.startListener(self.modulesUpdate)
        print "open"

    def onClose(self, wasClean, code, reason):
        facerecg.stopListener()
        print "close"

    def getPosCount(self):
        print "getPosCount"
        pos = {}
        pos['l'], pos['r'], pos['f'], needMore = facerecg.getPosCount()
        self.sendSocketMessage("TRAINPROCESS", pos)
        if needMore:
            reactor.callLater(0.3, self.getPosCount)

    def onMessage(self, payload, binary):
        raw = payload.decode('utf8')
        msg = json.loads(raw)
        if msg['type'] == "CONNECT_REQ":
            self.sendSocketMessage("CONNECT_RESP", msg)
        elif msg['type'] == "LOADNAME_REQ":
            names = facerecg.getNames()
            self.sendSocketMessage("LOADNAME_RESP", ",".join(names))
            if video_device == "laptop":
                self.sendSocketMessage("INITCAMERA")
            else:
                self.sendSocketMessage("INITVIDEO")
        elif msg['type'] == "DELETENAME_REQ":
            name = msg['msg'].encode('ascii', 'ignore')
            ret = facerecg.deleteName(name)
            if (ret != True):
                self.sendSocketMessage("ERROR_MSG", name + " is not in database")
        elif msg['type'] == "RECGFRAME_REQ":
            self.proWebFrame(msg['dataURL'])
            ret = facerecg.getResult()
            if ret is not None:
                self.sendSocketMessage("RECGFRAME_RESP", ret)
        elif msg['type'] == "TRAINSTART_REQ":
            name = msg['msg'].encode('ascii', 'ignore')
            ret = facerecg.trainStart(name)
            if (ret != True):
                self.sendSocketMessage("ERROR_MSG", name + " is already in database")
            else:
                self.sendSocketMessage("TRAINSTART_RESP")
                reactor.callLater(0.3, self.getPosCount)
        elif msg['type'] == "TRAINFINISH_REQ":
            print("TRAINFINISH_REQ ignore")

    def sendSocketMessage(self, mtype, msg = ""):
        msg = { "type" : mtype, 'msg' : msg }
        self.sendMessage(json.dumps(msg))

    def proWebFrame(self, dataURL):
        head = "data:image/jpeg;base64,"
        assert(dataURL.startswith(head))
        imgdata = base64.b64decode(dataURL[len(head):])
        imgf = Image.open(StringIO.StringIO(imgdata))
        facerecg.proImageFile(imgf)

fdir = os.path.dirname(os.path.realpath(__file__))
tls_crt = os.path.join(fdir, 'tls', 'server.crt')
tls_key = os.path.join(fdir, 'tls', 'server.key')


def startSocketServer():
    factory = WebSocketServerFactory()
    factory.protocol = FaceServerProtocol
    ctx_factory = DefaultOpenSSLContextFactory(tls_key, tls_crt)
    reactor.listenSSL(9000, factory, ctx_factory)
    reactor.run()

def startWebSocketServer(tls_key, tls_crt, dev):
    global video_device
    video_device = dev
    p2 = Process(target = startSocketServer)
    p2.start()

