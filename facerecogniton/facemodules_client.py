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

url = 'http://10.193.20.77:8383/train'
train_images = []
train_name = ""

def get_person_names():
    names = []
    for name in feature_data_set:
        names.append(name)
    return names

def delete_person_name(name):
    if (has_name(name)):
        args = {'id': name}
        headers = {"Content-type":"application/json","Accept": "application/json"}
        r = requests.delete(url, params=args, headers=headers)
        return True
    else
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
    return PersonModel(name)

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
    headers = {"Content-type":"application/json","Accept": "application/json"}
    r = requests.get(url, headers=headers)

def modules_init(serverip='localhost'):
    f = open('./models/facerec_128D.txt','r');
    feature_data_set = json.loads(f.read());
    global url = 'http://{}:8383/train'.format(serverip)
