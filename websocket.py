import json
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

from multiprocessing import Process

class FaceServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        super(FaceServerProtocol, self).__init__()
        self.new_person = None
        self.peoples = []
        reactor.callLater(1,self.timerCallback)

    def timerCallback(self):
        reactor.callLater(1,self.timerCallback)

    def onOpen(self):
        print "open"

    def onClose(self, wasClean, code, reason):
        print "close"

    def onMessage(self, payload, binary):
        raw = payload.decode('utf8')
        msg = json.loads(raw)
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
        elif msg['type'] == "TRAINSTART_REQ":
            name = msg['msg'].encode('ascii', 'ignore')
            if (name in self.peoples):
                self.sendSocketMessage("ERROR_MSG", name + " is already in database")
            else:
                #ret = self.sendQueueMessage("TRAINSTART_REQ", name)
                self.sendSocketMessage(ret["type"], ret["msg"])
        elif msg['type'] == "TRAINFINISH_REQ":
            #ret = self.sendQueueMessage("TRAINFINISH_REQ")
            self.sendSocketMessage(ret["type"], ret["msg"])

    def sendSocketMessage(self, mtype, msg = ""):
        msg = { "type" : mtype, 'msg' : msg }
        print("send sendSocketMessage:",json.dumps(msg))
        self.sendMessage(json.dumps(msg))

def socketServerProcess():
    factory = WebSocketServerFactory("ws://localhost:9000")
    factory.protocol = FaceServerProtocol
    listenWS(factory)
    reactor.run()

def startWebSocketServer():
    p2 = Process(target = socketServerProcess)
    p2.start()

