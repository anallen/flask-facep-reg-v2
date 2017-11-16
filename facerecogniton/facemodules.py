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


'''
Description:
Images from Video Capture -> detect faces' regions -> crop those faces and align them 
    -> each cropped face is categorized in 3 types: Center, Left, Right 
    -> Extract 128D vectors( face features)
    -> Search for matching subjects in the dataset based on the types of face positions. 
    -> The preexisitng face 128D vector with the shortest distance to the 128D vector of the face on screen is most likely a match
    (Distance threshold is 0.6, percentage threshold is 70%)
    
'''

def detect_people(frame):
    rets = []
    rects, landmarks = face_detect.detect_face(frame,40);#min face size is set to 80x80
    for (i,rect) in enumerate(rects):
        rets.append({"name":"   ", "pos":rect})

    return rets

def recog_process_frame(frame):
    rects, landmarks = face_detect.detect_face(frame,40);#min face size is set to 80x80
    aligns = []
    positions = []
    rets = []
    for (i, rect) in enumerate(rects):
        aligned_face, face_pos = aligner.align(160,frame,landmarks[i])
        aligns.append(aligned_face)
        positions.append(face_pos)
    if (len(aligns) == 0):
        return rets
    features_arr = extract_feature.get_features(aligns)
    recog_data = findPeople(features_arr,positions);
    for (i,rect) in enumerate(rects):
        rets.append({"name":recog_data[i], "pos":rect})
    return rets

'''
facerec_128D.txt Data Structure:
{
"Person ID": {
    "Center": [[128D vector]],
    "Left": [[128D vector]],
    "Right": [[128D Vector]]
    }
}
This function basically does a simple linear search for 
^the 128D vector with the min distance to the 128D vector of the face on screen
'''
def findPeople(features_arr, positions, thres = 0.6, percent_thres = 90):
    '''
    :param features_arr: a list of 128d Features of all faces on screen
    :param positions: a list of face position types of all faces on screen
    :param thres: distance threshold
    :return: person name and percentage
    '''
    regRes = [];
    for (i,features_128D) in enumerate(features_arr):
        returnRes = "Unknown";
        smallest = sys.maxsize
        for person in feature_data_set.keys():
            person_data = feature_data_set[person][positions[i]];
            for data in person_data:
                distance = np.sqrt(np.sum(np.square(data-features_128D)))
                if(distance < smallest):
                    smallest = distance;
                    returnRes = person;
        percentage =  min(100, 100 * thres / smallest)
        if percentage <= percent_thres :
            regRes.append("Unknown")
        else:
            regRes.append(returnRes+"-"+str(round(percentage,1))+"%")
    return regRes

'''
Description:
User input his/her name or ID -> Images from Video Capture -> detect the face -> crop the face and align it 
    -> face is then categorized in 3 types: Center, Left, Right 
    -> Extract 128D vectors( face features)
    -> Append each newly extracted face 128D vector to its corresponding position type (Center, Left, Right)
    -> Press Q to stop capturing
    -> Find the center ( the mean) of those 128D vectors in each category. ( np.mean(...) )
    -> Save
    
'''
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

def has_name(name):
    return feature_data_set.has_key(name)

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
