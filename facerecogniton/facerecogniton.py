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
import boto3
from email.mime.text import MIMEText
import smtplib, time

Global = Manager().Namespace()

from_addr = 'gf_dlut@126.com'
password = 'b41466'
smtp_server = 'smtp.126.com'
to_addr = "mingkai.hu@nxp.com"
smtpserver = None
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
        
        print("Face recognition engine initialized")
        print("Please open browser and visite https://[board-ip]:5000/")
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

def proCvFrame(frame):
    global nextprocess
    fq = frameq[nextprocess]
    try:
        if (fq.full()):
            fq.get_nowait()
        fq.put((Global.training, frame, Global.needUpdate[nextprocess]))
        nextprocess = (nextprocess + 1) % processnum
        if Global.training:
            facemodules.training_proframe(Global.training_name, frame)
    except Exception as e:
        print(e)

def trainStart(name):
    if(Global.training or Global.training_name):
        return False
    facemodules.training_start(name)
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
            print "training_finish",poscnt
            if poscnt[rets[0]["pos"]] < 15:
                poscnt[rets[0]["pos"]] += 1
                Global.poscount = poscnt
            if poscnt["Left"] == 15 and poscnt["Right"] == 15 and poscnt["Center"] == 15:
                print "training_finish"
                facemodules.training_finish(Global.training_name)
                Global.training = False
        nextresult = (nextresult + 1) % processnum
        if len(rets) == 1 and rets[0]["pos"] == "Center":
            snsmqttclient.publish("/fr/name", rets[0]["name"]);
        return rets
    except Exception as e:
        print e
        return None

def getPosCount():
    return Global.poscount["Left"], Global.poscount["Right"], Global.poscount["Center"], Global.training

deleteName = facemodules.delete_module
getNames = facemodules.get_names

def onModuleUpdated(c, d, m):
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

door_stat = '0'
history_names = []
count = 0
def on_sns_message(client, userdata, message):
    global door_stat,history_names,count

    if message.topic == "/fr/door":
        door_stat = message.payload
        print("Get door msg", door_stat)
        if door_stat == '0':
            history_names = []
            count = 0
            mqttclient.publish("topic_state_door_close", "no use")
        else:
            mqttclient.publish("topic_state_door_open", "no use")
    elif message.topic == "/fr/name" and  door_stat == '1' and count < 5:
        name = message.payload
        count += 1
        if name not in history_names:
            history_names.append(name)

        if count < 5:
            return

        msgname = ""
        for key in history_names:
            msgname += key
        if " " in history_names and (msgname == "" or msgname == " "):
            msgname = "Unknown person"
        try:
            t = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
            msg = t + "--" + msgname + " has entered factory in Las Vegas."
            mqttclient.publish("topic_state_people_recg", msg)
            print(msg)
            #sns_client = boto3.client('sns', region_name='us-west-2')
            #response = sns_client.publish(PhoneNumber='+8613811968095', Message=msg)
            mailmsg = MIMEText(msg, 'plain', 'utf-8')
            mailmsg['from'] = from_addr
            mailmsg['to'] = to_addr
            smtpserver.sendmail(from_addr, to_addr, mailmsg.as_string())
        except Exception as e:
            print(e)

def onMqttConnect(client, userdata, flags, rc):
    print('Connected to MQTT broker with error code:' + str(rc))

def startListener(cb):
    global mqttclient, callback, snsmqttclient, smtpserver
    if mqttclient is not None:
        return
    mqttclient = mqtt.Client()
    mqttclient.on_message = onModuleUpdated
    mqttclient.on_connect = onMqttConnect
    mqttclient.connect(serverip, 1883, 60)
    mqttclient.loop_start()
    mqttclient.subscribe("NXP_FACE_RECG_MODULES_UPDATED", qos=1)
    callback = cb

    snsmqttclient = mqtt.Client()
    snsmqttclient.connect("localhost", 1883, 60)
    snsmqttclient.on_message = on_sns_message
    snsmqttclient.subscribe("/fr/door", qos=1)
    snsmqttclient.subscribe("/fr/name", qos=1)
    snsmqttclient.loop_start()

    print("Connecting SMTP mail server")
    smtpserver = smtplib.SMTP(smtp_server, 25)
    smtpserver.login(from_addr, password)
    print("ConnectedSMTP mail server")
    

def stopListener():
    global mqttclient, callback
    if mqttclient is None:
        return
    mqttclient.disconnect()
    mqttclient = None
    callback = None

#initEngine(server='10.193.20.77')
initEngine(server='ec2-35-161-19-251.us-west-2.compute.amazonaws.com')
