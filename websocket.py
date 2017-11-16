import json
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS
from twisted.internet import task, defer

from twisted.internet.ssl import DefaultOpenSSLContextFactory
from facerecogniton.facerecogniton import facerecg
from multiprocessing import Process
import time, StringIO, base64, os
from PIL import Image
import threading



class FaceServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        super(FaceServerProtocol, self).__init__()
        self.new_person = None
        self.peoples = []
        #self.t = threading.Thread(target=self.getResultThread)
        #self.t.start()

    def getResultThread(self):
        while (1):
            rets = facerecg.getResult()
            self.sendSocketMessage("RECGFRAME_RESP", rets)

    def onOpen(self):
        print "open"

    def onClose(self, wasClean, code, reason):
        print "close"

    def onMessage(self, payload, binary):
        raw = payload.decode('utf8')
        msg = json.loads(raw)
        #print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())),
        #       "get message type=" + msg['type'])
        if msg['type'] == "CONNECT_REQ":
            self.sendSocketMessage("CONNECT_RESP")
        elif msg['type'] == "LOADNAME_REQ":
            #ret = self.sendQueueMessage("LOADNAME_REQ")
            #self.peoples = ret['msg']
            self.peoples = ['gf']
            self.sendSocketMessage("LOADNAME_RESP", self.peoples)
        elif msg['type'] == "DELETENAME_REQ":
            name = msg['msg'].encode('ascii', 'ignore')
            if (name in self.peoples):
                #ret = self.sendQueueMessage("DELETENAME_REQ", name)
                self.peoples = ret['msg']
                self.sendSocketMessage(ret["type"], ret["msg"])
            else:
                self.sendSocketMessage("ERROR_MSG", name + " is not in database")
        elif msg['type'] == "RECGFRAME_REQ":
            self.proWebFrame(msg['dataURL'])
            rets = facerecg.getResult()
            if rets is not None:
                self.sendSocketMessage("RECGFRAME_RESP", rets)
        elif msg['type'] == "TRAINSTART_REQ":
            name = msg['msg'].encode('ascii', 'ignore')
            if (name in self.peoples):
                elf.sendSocketMessage("ERROR_MSG", name + " is already in database")
            else:
                #ret = self.sendQueueMessage("TRAINSTART_REQ", name)
                self.sendSocketMessage(ret["type"], ret["msg"])
        elif msg['type'] == "TRAINFINISH_REQ":
            #ret = self.sendQueueMessage("TRAINFINISH_REQ")
            self.sendSocketMessage(ret["type"], ret["msg"])

    def sendSocketMessage(self, mtype, msg = ""):
        msg = { "type" : mtype, 'msg' : msg }
        #print("send sendSocketMessage:",json.dumps(msg))
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

def startWebSocketServer(tls_key, tls_crt):
    p2 = Process(target = startSocketServer)
    p2.start()

