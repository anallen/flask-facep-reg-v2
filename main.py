#!/usr/bin/env python
from importlib import import_module
import os,time
from flask import Flask, render_template, Response
from websocket import startWebSocketServer


#from camera_opencv import *

fdir = os.path.dirname(os.path.realpath(__file__))
tls_crt = os.path.join(fdir, 'tls', 'server.crt')
tls_key = os.path.join(fdir, 'tls', 'server.key')

app = Flask(__name__)

@app.route('/')
def index():
    """Video streaming home page."""
    #return render_template('index_opencv.html')
    return render_template('index_web.html')


def gen(camera):
    """Video streaming generator function."""
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')

@app.route('/videoel')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    startWebSocketServer(tls_key, tls_crt)
    #app.run(host='0.0.0.0', threaded=True)
    app.run(host='0.0.0.0', threaded=True, ssl_context=(tls_crt, tls_key))

