import cv2
from base_camera import BaseCamera
from facerecogniton.facerecogniton import facerecg
import Queue


class Camera(BaseCamera):
    video_source = 'rtsp://admin:china123@192.168.1.13:554/mpeg/ch1/sub/av_stream'
    reg_ret = []

    @staticmethod
    def set_video_source(source):
        Camera.video_source = source

    @staticmethod
    def frames():
        global facerecg
        frameq = Queue.Queue(maxsize=10)
        camera = cv2.VideoCapture(Camera.video_source)
        #camera.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        #camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
        #camera.set(cv2.CAP_PROP_FPS, 30)
        current_frame = 0

        if not camera.isOpened():
            raise RuntimeError('Could not start camera.')

        while True:
            
            # read current frame
            _, img = camera.read()
	    frameq.put(img)
            facerecg.doRecognition(img)

            if (frameq.full()):
                img = frameq.get()
            ret = facerecg.getResult()
            if ret is not None:
                Camera.reg_ret = ret
            for ret in Camera.reg_ret:
                #draw bounding box for the face
                rect = ret['pos']
                cv2.rectangle(img,(rect[0],rect[1]),(rect[0] + rect[2],rect[1]+rect[3]),(0,0,255),2)
                cv2.putText(img, ret['name'],(rect[0],rect[1]),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)


            # encode as a jpeg image and return it
            yield cv2.imencode('.png', img)[1].tobytes()
