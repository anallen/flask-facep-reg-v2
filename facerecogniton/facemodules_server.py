'''
Main program
@Author: David Vu

To execute simply run:
main.py

To input new user:
main.py --mode "input"

'''

import cv2
from align_custom import AlignCustom
from face_feature import FaceFeature
from mtcnn_detect import MTCNNDetect
from tf_graph import FaceRecGraph
import argparse
import sys, time
import json
import numpy as np
from PIL import Image
import StringIO

FRGraph = FaceRecGraph();
aligner = AlignCustom();
extract_feature = FaceFeature(FRGraph)
face_detect = MTCNNDetect(FRGraph, scale_factor=2); #scale_factor, rescales image for faster detection
feature_data_set = None



class PersonModel:
    def __init__(self, name):
        self.name = name
        self.person_imgs = {"Left" : [], "Right": [], "Center": []};
        self.feature = None
        self.images = []

def training_start_local(name):
    if(has_name(name)):
        return None
    return PersonModel(name)

def training_proframe_local(model, frame):
    rects, landmarks = face_detect.detect_face(frame, 80);  # min face size is set to 80x80
    for (i, rect) in enumerate(rects):
        aligned_frame, pos = aligner.align(160,frame,landmarks[i]);
        model.person_imgs[pos].append(aligned_frame)
    for (i,rect) in enumerate(rects):
        cv2.rectangle(frame,(rect[0],rect[1]),(rect[0] + rect[2],rect[1]+rect[3]),(255,0,0))
    return frame

def __training_thread_local(model, callback):
    person_features = {"Left" : [], "Right": [], "Center": []};
    for pos in model.person_imgs:
        person_features[pos] = [np.mean(extract_feature.get_features(
                                         model.person_imgs[pos]),axis=0).tolist()]
    if (feature_data_set is not None):
        __save_person_features(model.name, person_features)
    callback(model.name, person_features)

def training_finish_local(model, callback):
    t = threading.Thread(target=__training_thread_local, args=(model, callback,))
    t.start()
    return t

def __save_person_features(name, features):
    feature_data_set[name] = features;
    f = open('./models/facerec_128D.txt', 'w');
    f.write(json.dumps(feature_data_set))

def get_person_names():
    names = []
    for name in feature_data_set:
        names.append(name)
    return names

def delete_person_name(name):
    if (has_name(name)):
        del feature_data_set[name];
        f = open('./models/facerec_128D.txt', 'w');
        f.write(json.dumps(feature_data_set))

import requests
import threading

url = 'http://10.193.20.74:8383/train'

def __training_thread_remote(model, callback):
    args = {'id': model.name, 'end':'true'}
    headers = {"Content-type":"application/json","Accept": "application/json"}
    files = {}
    for i,f in enumerate(model.images):
        files['file{}'.format(i)] = ('{}.png'.format(i), f, 'image/png')
    r = requests.post(url, params=args, files=files)

    args = {'id': model.name}
    headers = {"Content-type":"application/json","Accept": "application/json"}
    while (True):
        time.sleep(1)
        r = requests.get(url, params=args, headers=headers)
        ret = json.loads(r.text)
        if ('state'in ret and ret['state'] == 'FINISH'):
            __save_person_features(model.name, ret['feature'])
            callback(model.name, r.text)
            headers = {"Content-type":"application/json","Accept": "application/json"}
            r = requests.delete(url, params=args, headers=headers)
            break

def training_start_remote(name):
    args = {'id': name}
    headers = {"Content-type":"application/json","Accept": "application/json"}
    r = requests.put(url, params=args, headers=headers)
    return PersonModel(name)

def training_proframe_remote(model, frame):
    picf = StringIO.StringIO()
    pi = Image.fromarray(frame)
    pi.save(picf, format = "jpeg")
    picf.seek(0)

    model.images.append(picf)

def training_finish_remote(model, callback):
    t = threading.Thread(target=__training_thread_remote, args=(model, callback,))
    t.start()
    return t

training_start = training_start_local
training_proframe = training_proframe_local
training_finish = training_finish_local

def recog_engine_init(serverip=None):
    global training_start, training_proframe, training_finish
    if (serverip is not None):
        global url
        url = 'http://{}:8383/train'.format(serverip)
        training_start = training_start_remote
        training_proframe = training_proframe_remote
        training_finish = training_finish_remote
    global feature_data_set

def load_modules():
    f = open('./models/facerec_128D.txt','r');
    feature_data_set = json.loads(f.read());
