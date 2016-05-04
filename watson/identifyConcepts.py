# -*- coding: utf-8 -*-
#	Copyright 2016 IBM Corporation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""
Created on Tue Apr 12 15:57:00 2016

@author: priscillamoraes
"""

import json
import subprocess
import shlex
import glob
import os

from alchemyapi import AlchemyAPI
alchemyapi = AlchemyAPI()

   
actionMessages = []
allMessages = []

NLC_URL="https://gateway.watsonplatform.net/natural-language-classifier/api/v1/classifiers/"
NLC_CLASSIFIER="f15e67x54-nlc-4751"
NLC_CREDS="0cff2e79-2b9e-4ed2-b200-598593755474:GIbzM6frd0Lg"

CI_URL="https://gateway.watsonplatform.net/concept-insights/api",
CI_CREDS="bf566743-7e51-4c17-9553-ca778c0c346a:bGPQKlpeqXyz"
CI_UPDATEDOC_URL="https://gateway.watsonplatform.net/concept-insights/api/v2/corpora/sion2fac7fa3/slackIBM/documents/"

OUTPUT_DIR="/Users/priscillamoraes/Documents/work/Ecosystem/Slack/data/ibmcicontentplain"

SLACK_API_TOKEN_ECO="xoxp-19715880850-26863632519-36432026401-b70bc3418c"
SLACK_API_TOKEN_SLACKER="xoxp-34402827254-34409890672-36426885575-e8fce120c6"
SLACK_URL="https://slack.com/api/search.messages?"

class IdentifyConcepts:
    
    def __init__(self):
        print("Initialized Concept Identification")
        
    def stripSpecial(self, myString):
        return myString.replace('\n', ' ').replace('"', ' ').replace('!', ' ').replace('@', ' ').replace('#', ' ') \
            .replace('$', ' ').replace('%', ' ').replace('^', ' ').replace('&', ' ').replace('*', ' ').replace('(', ' ') \
            .replace(')', ' ').replace('<', ' ').replace('>', ' ').replace('/', ' ').replace('\\', ' ').replace('[', ' ') \
            .replace(']', ' ').replace('{', ' ').replace('}', ' ').replace('|', ' ').replace(':', ' ').replace(';',' ') \
            .replace(',',' ').replace('-',' ').replace('+',' ').replace('=',' ').replace('~',' ').replace('_',' ').replace('\'','')
            
    def createDocument(self, folder):
        folders = os.listdir(folder)
        documentContent = ""
        for dirName in folders:
            fileNumber = 0
            files = glob.glob(folder+"/"+dirName+"/*.json")
            for fileName in files:
                messages = json.load(open(fileName))
                for message in messages:
                    if 'subtype' not in message:
                        documentContent += " "+message['text']
                documentContent = self.stripSpecial(documentContent.encode('ascii', 'ignore').decode('ascii'))
                f1=open(OUTPUT_DIR+'/'+dirName+str(fileNumber)+'.txt', 'w+')
                f1.write(documentContent)
                f1.close()
                fileNumber += 1
                
    #it uploads json documents to the corpus
    def uploadDocument(self, folder):
        files = glob.glob(folder+"/*.txt")
        response = {}
        for fileName in files:
            print os.path.basename(fileName)
            name = os.path.basename(fileName)
            curl_cmd = 'curl -X PUT -u "%s" -d @%s %s%s' % (CI_CREDS, name, CI_UPDATEDOC_URL, name.replace('.txt',''))
            print curl_cmd
            process = subprocess.Popen(shlex.split(curl_cmd), stdout=subprocess.PIPE)
            output = process.communicate()[0]
            try:
                response = json.loads(output)
            except:
                print ('Command:')
                print (curl_cmd)
                print ('Response:')
                print (response)
                
    def searchMessages(self, keywords, token):
        query = keywords.replace(" ","%20")
        curl_cmd = 'curl -X GET "%stoken=%s&query=%s&pretty=1"' % (SLACK_URL, token, query)
        print curl_cmd
        process = subprocess.Popen(shlex.split(curl_cmd), stdout=subprocess.PIPE)
        output = process.communicate()[0]
        try:
            slackSearch = json.loads(output)
            return slackSearch
        except:
            print ('Command:')
            print (curl_cmd)
            print ('Response:')
            print (slackSearch)
            return None
        
    
        
    def getChannels(self, searchResults):
        #channelFreq = defaultdict(dict)
        channelFreq = {}
        if searchResults['ok'] == True:
            messages = searchResults['messages']
            if messages is not None:
                matches = messages['matches']
            else:
                return None
            print "Matches: "+str(len(matches))
            for match in matches:
                channel = match['channel']
                print "Channel: "+str(channel)
                if channel is None:
                    return None
                else:
                    channelName = channel['name']
                    print "Channel name: "+channelName
                    if channelName is not None:
                        if channelName in channelFreq.keys():
                            channelFreq[channelName] = channelFreq[channelName] + 1
                        else:
                            channelFreq[channelName] = 1
            print "Channel name dictionary: "+str(channelFreq)
            return channelFreq
        else:
            return None
           
    def getTopNChannels(self, numberOfChannels, channels):
        channelsNames = []
        tempChannels = channels
        tempCount = 0
        tempChannel = ""
        if len(channels) > 0:        
            while numberOfChannels > 0:        
                for key, value in tempChannels.items():
                    if value > tempCount and 'general' not in key:
                        tempCount = value
                        tempChannel = key
                if tempChannel is not "":
                    channelsNames.append(tempChannel)
                try:
                    del tempChannels[tempChannel]
                except KeyError:
                    pass
                tempCount = 0
                tempChannel = ""
                numberOfChannels -= 1
        return channelsNames
