'''
Main program
@Author: David Vu

To execute simply run:
main.py

To input new user:
main.py --mode "input"

'''

import cv2
import argparse
import sys, time
import json
import numpy as np
from PIL import Image
import StringIO
import requests
import threading

url = ''
train_images = []
train_name = ''
feature_data_set = {}

def get_names():
    names = []
    for name in feature_data_set:
        names.append(name)
    return names

def delete_module(name):
    if (feature_data_set is not None and name in feature_data_set):
        args = {'id': name}
        headers = {"Content-type":"application/json","Accept": "application/json"}
        r = requests.delete(url, params=args, headers=headers)
        ret = json.loads(r.text)
        if ('state'in ret and ret['state'] == 'SUCCESS'):
             return True
    return False

def __training_thread():
    args = {'id': train_images, 'end':'true'}
    headers = {"Content-type":"application/json","Accept": "application/json"}
    files = {}
    for i,f in enumerate(train_images):
        files['file{}'.format(i)] = ('{}.png'.format(i), f, 'image/png')
    r = requests.post(url, params=args, files=files)
    train_images = []
    train_name = ''

def training_start(name):
    args = {'id': name}
    train_name = name
    headers = {"Content-type":"application/json","Accept": "application/json"}
    r = requests.put(url, params=args, headers=headers)
    ret = json.loads(r.text)
    if ('state'in ret and ret['state'] == 'SUCCESS'):
        return True
    else:
        return False

def training_proframe(frame):
    picf = StringIO.StringIO()
    pi = Image.fromarray(frame)
    pi.save(picf, format = "jpeg")
    picf.seek(0)

    train_images.append(picf)

def training_finish():
    t = threading.Thread(target=__training_thread_remote)
    t.start()
    return t

def update_modules():
    global feature_data_set
    headers = {"Content-type":"application/json","Accept": "application/json"}
    r = requests.get(url, headers=headers)
    if (r.status_code == 200):
        f = open('./models/facerec_128D.txt','w');
        f.write(r.content)
        f.close()
        feature_data_set = json.loads(r.content);
        return True
    else:
        return False

def modules_init(serverip='localhost'):
    global url
    url  = 'http://{}:8383/train'.format(serverip)
    update_modules()
