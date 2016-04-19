# Copyright 2015 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
from flask import Flask,Response, request
from watson.classifyMessage import  ClassifyMessage

classifier = ClassifyMessage()

app = Flask(__name__)


@app.route('/')
def Welcome():
    return app.send_static_file('index.html')


@app.route('/myapp')
def WelcomeToMyapp():
    return 'Welcome again to my app running on Bluemix!'

@app.route('/classify')
def classify():
    print ("Request Received %s" % request.args['text'])
    text = request.args['text']
    classifiedText = classifier.classifyText(text)
    return Response(json.dumps(classifiedText), status=200, mimetype='application/json')

port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    print("Initializing...")
    classifier.classifyText('blah')
    app.run(host='0.0.0.0', port=int(port))


