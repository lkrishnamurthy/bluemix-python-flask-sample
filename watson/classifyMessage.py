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
import xml.etree.ElementTree
import re
import random
from sets import Set

from alchemyapi import AlchemyAPI
from identifyConcepts import *
from rtc.rtc_client import rtc_client

alchemyapi = AlchemyAPI()
ic = IdentifyConcepts()
rtcClient = rtc_client()

NLC_URL = "https://gateway.watsonplatform.net/natural-language-classifier/api/v1/classifiers/"
#NLC_CLASSIFIER="3a84dfx64-nlc-2405"
NLC_CLASSIFIER="3a84cfx63-nlc-3072"
NLC_CREDS = "0cff2e79-2b9e-4ed2-b200-598593755474:GIbzM6frd0Lg"

RE_URL = "https://gateway.watsonplatform.net/relationship-extraction-beta/api/v1/sire/0"
NEW_RE_URL = "http://laser1.watson.ibm.com/axis/ie.jsp"
RE_CREDS = "0cff2e79-2b9e-4ed2-b200-598593755474:GIbzM6frd0Lg"

SLACK_API_TOKEN_ECO="xoxp-19715880850-26863632519-36432026401-b70bc3418c"
SLACK_API_TOKEN_SLACKER="xoxp-34402827254-34409890672-36426885575-e8fce120c6"

OUTPUT_DIR = "Slack/results"


class ClassifyMessage:
    def __init__(self):
        print("Initialized Classifier")

    def stripSpecial(self, myString):
        return myString.replace('\n', ' ').replace('"', '').replace('!', '').replace('@', '').replace('\#', '') \
            .replace('$', '').replace('%', '').replace('^', '').replace('&', '').replace('*', '').replace('(', '') \
            .replace(')', '').replace('<', '').replace('>', '').replace('/', '').replace('\\', '').replace('[','') \
            .replace(']', '').replace('{', '').replace('}', '').replace('|', '').replace(':', '').replace(';', '') \
            .replace(',', ' ').replace('-', '').replace('+', '').replace('=', '').replace('~', '') \
            .replace('_','').replace('\'', '').replace('`','').replace("'","")

    def classifyText(self, text,store):
        newClassification = {}
        clauses = []
        tempClauses = []
        intents = []
        searchChannels = ""
        confidence = 1

        #Call Relatioship Extraction and get the sentences broken up
        #getting the sentences from parse
        text = text.encode('ascii', 'ignore').decode('ascii')
        text = self.stripSpecial(text)
        curl_cmd = 'curl -X POST -u %s %s -d "sid=ie-en-news" -d "txt=%s"' % (RE_CREDS, RE_URL, text)

        try:
            #curl_cmd = 'curl -F svcid=ie.en_klue3_crf_coord -F text="%s" %s' % (text, NEW_RE_URL)
            process = subprocess.Popen(shlex.split(curl_cmd), stdout=subprocess.PIPE)
            output = process.communicate()[0]
            f = open(OUTPUT_DIR+'/parse.txt', 'w+')
            f.write(output)
            f.close()
        except:
            print ('Command:')
            print (curl_cmd)
            print ('Response:')
            print (output)

        try:
            parsedXML = xml.etree.ElementTree.parse(OUTPUT_DIR + '/parse.txt').getroot()
            doc = parsedXML.find('doc')
            sents = doc.find('sents')
            for sentence in sents.findall('sent'):
                surface = sentence.find('text').text
                parse = sentence.find('parse').text
                # find main clauses separated by comma
                matchesList = re.findall('\,\_\, \[VP', parse)
                if len(matchesList) > 0:
                    for match in matchesList:
                        # break the sentence into individual clauses
                        tempClauses.extend(surface.split(","))
                else:
                    tempClauses.append(surface)
                for clause in tempClauses:
                    # find a coordinating conjunction connective
                    matchesCC = re.findall('[a-z]+_CC', parse)
                    if len(matchesCC) > 0:
                        for match in matchesCC:
                            # remove the connective syntactic tag
                            match = match.replace('_CC', '')
                            # break the sentence into individual clauses
                            clauses.extend(clause.split(" " + match + " "))
                    else:
                        clauses.append(clause)
            uniqueClauses = Set()
            for clause in clauses:
                uniqueClauses.add(clause)
            clauses = list(uniqueClauses)
            print "Clauses: " + str(len(clauses))
            print clauses

            newClassification['Message'] = text
        except:
            print ('Exception when obtaining the parse from RE service.')
            newClassification['Message'] = None
            
        #getting the sentiment of the message
        sentimentResponse = alchemyapi.sentiment("text", text)
        if sentimentResponse['status'] == 'OK':
            newClassification['Sentiment'] = sentimentResponse["docSentiment"]["type"]
        else:
            print('Error in sentiment identification call: ', sentimentResponse['statusInfo'])

        #getting the entities with sentiment from the message
        entityResponse = alchemyapi.entities('text', text, {'sentiment': 1})
        entities = []
        if entityResponse['status'] == 'OK':
            for entityEntry in entityResponse['entities']:
                entity = {}
                entity['text'] = entityEntry['text']
                entity['type'] = entityEntry['type']
                entity['relevance'] = entityEntry['relevance']
                entity['sentiment'] = entityEntry['sentiment']['type']
                if 'score' in entityEntry['sentiment']:
                    entity['sentiment score'] = entityEntry['sentiment']['score']
                entities.append(entity)
            newClassification['entities'] = entities
        else:
            print('Error in entity extraction call: ', entityResponse['statusInfo'])

        #getting the keywords with sentiment from the message
        keywordResponse = alchemyapi.keywords('text', text, {'sentiment': 1})
        keywords = []
        if keywordResponse['status'] == 'OK':
            for keywordEntry in keywordResponse['keywords']:
                keyword = {}
                keyword['text'] = keywordEntry['text'].encode('utf-8')
                searchChannels += keywordEntry['text'].encode('utf-8')+" "
                keyword['relevance'] = keywordEntry['relevance']
                keyword['sentiment'] = keywordEntry['sentiment']['type']
                if 'score' in keywordEntry['sentiment']:
                    keyword['sentiment score'] = keywordEntry['sentiment']['score']
                keywords.append(keyword)
            newClassification['keywords'] = keywords
        else:
            print('Error in keyword extaction call: ', keywordResponse['statusInfo'])

        #getting the NLC classification. It needs to be done by each clause individually
        #returns a list of nlc outputs and append it to the final object
        for clause in clauses:
            text = clause.encode('ascii', 'ignore').decode('ascii')
            nlcText = text.replace(" ","%20")
            request = NLC_URL+NLC_CLASSIFIER+"/classify?text="+nlcText
            request = request.strip()
            curl_cmd = 'curl -G -u %s %s' % (NLC_CREDS, request)
            process = subprocess.Popen(shlex.split(curl_cmd), stdout=subprocess.PIPE)
            output = process.communicate()[0]
            nlcClassification = None
            try:
                nlcClassification = json.loads(output)
            except:
                print ('Command:')
                print (curl_cmd)
                print ('Response:')
                print (output)
            nlc = {}
            if (nlcClassification is not None) and (nlcClassification['classes'] > 0):
                nlc['text'] = text
                nlc['class'] = nlcClassification['classes'][0]['class_name']
                nlc['confidence'] = nlcClassification['classes'][0]['confidence']
                if nlc['confidence'] < confidence:
                    confidence = nlc['confidence']
                intents.append(nlc)
        newClassification['Intents'] = intents
        newClassification['RelevantChannels'] = self.searchChannels(searchChannels)
        
        if "true" in store:
            return newClassification
        else:            
            print "Relevant channels: "+str(newClassification['RelevantChannels'])
            return self.postProcessor(newClassification, confidence)

    def searchChannels(self, keywords):
        channels = []
        teams = []
        response_eco = ic.searchMessages(keywords, SLACK_API_TOKEN_ECO)
        response_slacker = ic.searchMessages(keywords, SLACK_API_TOKEN_SLACKER)
        if response_eco is not None:
            channelFreq = {}
            channelFreq = ic.getChannels(response_eco)
            #print "ChannelFreq: "+str(channelFreq)
            if channelFreq is not None:            
                channels = ic.getTopNChannels(3, channelFreq)
        teams.append(channels)
        if response_slacker is not None:
            channelFreq = {}
            channelFreq = ic.getChannels(response_slacker)
            print "ChannelFreq: "+str(channelFreq)
            if channelFreq is not None:            
                channels = ic.getTopNChannels(3, channelFreq)
        teams.append(channels)
        print "Teams: "+str(teams)
        return teams

    def searchRtc(self, work_item_id):
        return rtcClient.get_work_item_status(work_item_id)

    def createWorkItem(self, title, summary):
        return rtcClient.create_work_item(title, summary)
        
    def postProcessor(self,response, confidence):
        action = {}
        intents = Set()
        actionIntentNames = ""
        botIntentNames = ""
        urls = ""
        numberIntents = 0
        actionIntents = Set()
        botIntents = Set()
        rtcQueryIntents = Set()
        rtcCreateIntents = Set()
        workItemNumber = []
        workItemDescription = ""
        answer = ""
        intentName = ""

        if (confidence > 0.8) and (confidence < 0.9):
            answer = "I am in training but here's my best guess: "
        if confidence <= 0.8:
            action['Message'] = "I have no idea..."
            return action['Message']
        if len(response['Intents']) > 1:

            # complex scenario: this loop is just separating the different intent types into sets
            for intent in response['Intents']:
                intentName = intent['class']
                intents.add(intentName)
                if ("box" in intentName) or ("badge" in intentName) or ("enterprise" in intentName) \
                    or ("travel" in intentName) or ("expenses" in intentName) or ("assets" in intentName) \
                    or ("procurement" in intent):
                    actionIntents.add(intentName)
                elif ("repository" in intentName) or ("scheduling" in intentName) or ("analytics" in intentName):
                    botIntents.add(intentName)
                elif ("query" in intentName):
                    rtcQueryIntents.add(intentName)
                    question = intent['text'].encode('ascii', 'ignore')
                    print "Question: "+question
                    workItems = re.findall('(\d+)', question)
                elif ("create" in intentName):
                    rtcCreateIntents.add(intentName)
                    question = intent['text'].encode('ascii', 'ignore')
                    workItemDescription = re.findall('\"(.+)\"', question)
            # post processing action intents (when a link is provided)
            for intent in actionIntents:
                if numberIntents == 0:
                    actionIntentNames = intent.replace('_', ' ')
                    urls = self.getUrl(intent)
                elif numberIntents + 1 == len(actionIntents):
                    actionIntentNames = actionIntentNames + " and " + intent.replace('_', ' ')
                    urls = urls + " and " + self.getUrl(intent)
                else:
                    actionIntentNames = actionIntentNames + ", " + intent.replace('_', ' ')
                    urls = urls + ", " + self.getUrl(intent)
                numberIntents += 1
            if numberIntents > 0:
                answer = answer+"I can help you right away with " + actionIntentNames + ". Just follow the link(s): " + urls

            # just providing a different answer when the intent needs a bot
            numberIntents = 0
            for intent in botIntents:
                if numberIntents == 0:
                    botIntentNames = intent.replace('_', ' ')
                    urls = self.getUrl(intent)
                elif numberIntents + 1 == len(botIntents):
                    botIntentNames = botIntentNames + " and " + intent.replace('_', ' ')
                    urls = urls + " and " + self.getUrl(intent)
                else:
                    botIntentNames = botIntentNames + ", " + intent.replace('_', ' ')
                    urls = urls + ", " + self.getUrl(intent)
                numberIntents += 1
            if len(botIntents) > 0 and answer is not "":
                answer = answer+" and for "+botIntentNames+" I found cool Bots that can help "+ urls
            elif len(botIntents) > 0:
                answer = "For " + botIntentNames + " I found cool Bots that can help " + urls
            print "Intents: "+str(intents)
            print "RTC Query Intents: "+str(rtcQueryIntents)
            print "Work Item Number: "+ str(workItemNumber)
            print "Work Item Description: " + str(workItemDescription)
            # actual implementation of the rtc bot (it makes calls to the Jazz API)
            if len(rtcQueryIntents) > 0:
                for intent in rtcQueryIntents:
                    if len(workItems) == 0:
                        answer = answer+' Regarding your RTC request, I need a work item number to fulfill your request'
                    else:
                        for workItem in workItems:
                            work_item_status = self.searchRtc(workItem)
                            if work_item_status is not None:
                                answer = answer+" According to RTC, the status of the work item " + workItem + "[ " + work_item_status["description"] + " ] is " + work_item_status["status"] + ".";
                            else:
                                status = " cannot be found or non-existent in RTC"
                                answer = answer+" Sorry, This work item " + workItem + status + "."
                    print "Answer: "+answer
            if len(rtcCreateIntents) > 0:
                for intent in rtcQueryIntents:
                    if workItemDescription is "":
                        answer = answer + ' For your RTC reques, please provide the information for the work item as: [title of work item : summary of the work item]'
                    else:
                        titleSummary = workItemDescription.split(":")
                        if len(titleSummary == 2):
                            wiCreationResponse = self.createWorkItem(titleSummary[0], titleSummary[1])
                        else:
                            answer = answer+" Please provide the information for the work item as: [title of work item : summary of the work item]"
                        if wiCreationResponse is None:
                            answer = answer +" Unable to create work item"
                        else:
                            answer = answer +" Work item created successfully"
                    print "Answer: " + answer
            action['Message'] = answer
        elif len(response['Intents']) == 1:
            intent = response['Intents'][0]
            intent = intent['class']
            messages = ["If I understand you correctly, you need help with ",
                        "It looks like you need help with ",
                        "I'm more than happy to help you with ", 
                        "It looks like you are looking for information about "]
            actionMessage = ["Here's what I found for you: ",
                             "This link might have the answer you are looking for ",
                             "Why don't you try this: "]
            botMessage = ["I found a Bot that can help you ",
                          "Try this cool Bot ",
                          "Why don't you try this Bot "]

            # if response['Sentiment'] is "negative":
            action['Severity'] = "high"
            url = self.getUrl(intent)
            action['URL'] = url
            intent = intent.replace('_', ' ')
            if ("box" in intent) or ("badge" in intent) or ("enterprise" in intent) \
                or ("travel" in intent) or ("expenses" in intent) or ("assets" in intent) \
                or ("procurement" in intent):
                action['Message'] = actionMessage[random.randint(0, len(actionMessage) - 1)] + url.encode('ascii', 'ignore').decode('ascii')
            #elif "po" in intent:
            #    queryIntent = response["Intents"]
            #    txt = queryIntent[0]['text'].encode('ascii', 'ignore')
            #    pos = re.findall('(\d+)', txt)
            #    if len(pos) > 0:
            #        action['Message'] = "Yes. PO "+pos[0]+" completed. Item is in stock. Shipped Date is 05/07/2016. Delivery estimated at 05/10/2016."
            #    else:
            #        action['Message'] = "For status of purchase orders, please provide an order number."
            elif "rtc" in intent:
                if "query" in intent:
                    # Get the intent for RTC Query for a Work Item
                    queryIntent = response["Intents"]
                    txt = queryIntent[0]['text'].encode('ascii','ignore')
                    pos = re.search('\d',txt)
                    if pos is None:
                        action['Message'] = 'Sorry. No work item number provided in the message'
                    else:
                        idx = pos.start()
                        if idx > 0:
                            work_item = txt[idx:idx+5]
                            work_item = work_item.strip();
                        # Check status in RTC using OSLC API
                        work_item_status = None
                        if work_item is not None:
                            work_item_status = self.searchRtc(work_item)
                        if work_item_status is not None:
                            action['Message'] = "According to RTC, the status of the work item " + work_item + " [ " + work_item_status["description"] + " ] is " + work_item_status["status"] + ".";
                        else:
                            status = " cannot be found or is non-existent in RTC"
                            action['Message'] = "Sorry, work item " + work_item + status + "."
                #elif "create" in intent:
                #    response = self.createWorkItem("Title test", "Summary test")
                #    print response
                #    action['Message'] = "Work item created successfully"
                    #createIntent = response["Intents"]
                    #description = re.findall("\"(.+)\"", createIntent[0]['text'].encode('ascii','ignore'))
                    #if len(description) > 0:
                        #titleSummary = description.split(":")
                        #if len(titleSummary == 2):
                        #    wiCreationResponse = self.createWorkItem(titleSummary[0], titleSummary[1])
                        #else:
                        #    action['Message'] = 'Please provide the information for the work item as: "title of work item : summary of the work item"'
                        #if wiCreationResponse is None:
                        #    action['Message'] = "Unable to create work item"
                        #else:
                        #    action['Message'] = "Work item created successfully"
                    #else:
                    #    action['Message'] = 'Please provide the information for the work item as: "title of work item : summary of the work item"'
                else:
                    action['Message'] = "I see you need to do something with RTC but could not quite get what it is."
            else:
                action['Message'] = messages[random.randint(0, len(messages) - 1)] + intent + ". " + botMessage[
                    random.randint(0, len(botMessage) - 1)] + url.encode('ascii', 'ignore').decode('ascii')
        else:
            return None

        #adding relevant channels to the answer
        try:
            relevantChannels = response['RelevantChannels']
            print str(relevantChannels)
            if len(relevantChannels[0]) + len(relevantChannels[1]) > 0:
                channels = ""
                channelsMessage = "I also found other channels discussing about this post. Consider joining the channels: ["
                numberOfChannels = 0                
                for channel in relevantChannels[1]:
                    if numberOfChannels == 0:
                        channels = "SlackerDemo:"+channel
#                    elif numberOfChannels + 1 == len(relevantChannels):
#                        channels = channels + " and " + channel
                    else:
                        channels = channels + ", " + "SlackerDemo:"+channel
                    numberOfChannels += 1
                print "Channels after SlackerDemo "+channels 
                for channel in relevantChannels[0]:
                    if channels is "":
                        channels = "IBM Watson Ecosystem:"+channel
#                    elif numberOfChannels + 1 == len(relevantChannels):
#                        channels = channels + " and " + channel
                    else:
                        channels = channels + ", " + "IBM Watson Ecosystem:"+channel
                print channels
                channelsMessage = channelsMessage+channels+"]"
                print channelsMessage
                action['Message'] = str(action['Message'])+" "+channelsMessage
                print "Final action: "+action['Message']
                return action['Message']
        except:
            print "Trouble appending relevant channels to the answer"
        return action['Message']

    def getUrl(self,intent):
        if intent == 'repository':
            url = "https://slackerdemo.slack.com/apps/new/A0F7XDU93-hubot"
        elif intent == 'scheduling':
            url = "https://meekan.com/slack/?ref=slackappstore"
        elif intent == 'enterprise_directory':
            url = "https://w3-03.sso.ibm.com/bluepages/index.wss"
        elif intent == 'analytics':
            url = "https://statsbot.co/?ref=slackappstore"
        elif intent == 'badge':
            url = "http://w3-03.ibm.com/security/secweb.nsf/ContentDocsByCtryTitle/United+States~Badge+request+and+administration"
        elif intent == 'box_notes':
            url = "https://www.box.com/notes/"
        elif intent == 'travel':
            url = "http://w3-01.ibm.com/hr/web/travel/index.html"
        elif intent == 'expenses':
            url = "http://w3-01.ibm.com/hr/web/expenses/"
        elif intent == 'assets':
            url = "https://w3-03.sso.ibm.com/tools/assets/eamt/index.jsp"
        elif intent == 'procurement':
            url = "https://w3-01.sso.ibm.com/procurement/buyondemand/"
        else:
            url = None
        return url
