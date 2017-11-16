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
import argparse
import sys, time
import json
import numpy as np
from PIL import Image
import StringIO

#FRGraph = FaceRecGraph();
aligner = AlignCustom();
extract_feature = FaceFeature()
face_detect = MTCNNDetect(scale_factor=2); #scale_factor, rescales image for faster detection
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
        rets.append({"name":recog_data[i], "rect":rect})
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
        returnRes = " ";
        smallest = sys.maxsize
        for person in feature_data_set.keys():
            person_data = feature_data_set[person][positions[i]];
            for data in person_data:
                distance = np.sqrt(np.sum(np.square(data-features_128D)))
                if(distance < smallest):
                    smallest = distance;
                    returnRes = person;
        percentage =  min(100, 100 * thres / smallest)
        if percentage > percent_thres :
            regRes.append(returnRes+"-"+str(round(percentage,1))+"%")
        else:
            regRes.append(" ")
    return regRes

def detect_people(frame):
    rects, landmarks = face_detect.detect_face(frame,40);#min face size is set to 80x80
    aligns = []
    positions = []
    rets = []
    for (i, rect) in enumerate(rects):
        aligned_face, face_pos = aligner.align(160,frame,landmarks[i])
        rets.append({"name":"", "rect":rect, 'pos':face_pos})
    return rets


def load_modules():
    global feature_data_set
    f = open('./models/facerec_128D.txt','r');
    feature_data_set = json.loads(f.read());
    f.close()
