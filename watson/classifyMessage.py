# -*- coding: utf-8 -*-
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

alchemyapi = AlchemyAPI()

actionMessages = []
allMessages = []

NLC_URL = "https://gateway.watsonplatform.net/natural-language-classifier/api/v1/classifiers/"
NLC_CLASSIFIER="f1704ex55-nlc-5545"
#NLC_CLASSIFIER = "f15e67x54-nlc-4751"
NLC_CREDS = "0cff2e79-2b9e-4ed2-b200-598593755474:GIbzM6frd0Lg"

RE_URL = "https://gateway.watsonplatform.net/relationship-extraction-beta/api/v1/sire/0"
RE_CREDS = "0cff2e79-2b9e-4ed2-b200-598593755474:GIbzM6frd0Lg"

OUTPUT_DIR = "Slack/results"


class ClassifyMessage:
    def __init__(self):
        print("Initialized Classifier")

    def stripSpecial(myString):
        return myString.replace('\n', ' ').replace('"', ' ').replace('!', ' ').replace('@', ' ').replace('#', ' ') \
            .replace('$', ' ').replace('%', ' ').replace('^', ' ').replace('&', ' ').replace('*', ' ').replace('(', ' ') \
            .replace(')', ' ').replace('<', ' ').replace('>', ' ').replace('/', ' ').replace('\\', ' ').replace('[',
                                                                                                                ' ') \
            .replace(']', ' ').replace('{', ' ').replace('}', ' ').replace('|', ' ').replace(':', ' ').replace(';', ' ') \
            .replace(',', ' ').replace('-', ' ').replace('+', ' ').replace('=', ' ').replace('~', ' ').replace('_',
                                                                                                               ' ').replace(
            '\'', '')

    def classifyText(self, text,store):
        newClassification = {}
        clauses = []
        tempClauses = []
        intents = []

        #Call Relatioship Extraction and get the sentences broken up
        #getting the sentences from parse
        text = text.encode('ascii', 'ignore').decode('ascii')
        curl_cmd = 'curl -X POST -u %s %s -d "sid=ie-en-news" -d "txt=%s"' % (RE_CREDS, RE_URL, text)
        process = subprocess.Popen(shlex.split(curl_cmd), stdout=subprocess.PIPE)
        output = process.communicate()[0]
        f = open(OUTPUT_DIR+'/parse.txt', 'w+')
        f.write(output)
        f.close()

        parsedXML = xml.etree.ElementTree.parse(OUTPUT_DIR+'/parse.txt').getroot()
        doc = parsedXML.find('doc')
        sents = doc.find('sents')
        for sentence in sents.findall('sent'):
            surface = sentence.find('text').text
            parse = sentence.find('parse').text
            #find main clauses separated by comma
            matchesList = re.findall('\,\_\, \[VP', parse)
            if len(matchesList) > 0:
                for match in matchesList:
                    #break the sentence into individual clauses
                    tempClauses.extend(surface.split(","))
            else:
                tempClauses.append(surface)
            for clause in tempClauses:
                #find a coordinating conjunction connective
                matchesCC = re.findall('[a-z]+_CC', parse)
                if len(matchesCC) > 0:
                    for match in matchesCC:
                    #remove the connective syntactic tag
                        match = match.replace('_CC','')
                        #break the sentence into individual clauses
                        clauses.extend(clause.split(" "+match+" "))
                else:
                    clauses.append(clause)
        uniqueClauses = Set()
        for clause in clauses:
            uniqueClauses.add(clause)
        clauses = list(uniqueClauses)
        print "Clauses: "+str(len(clauses))
        print clauses

        newClassification['Message'] = text

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
            try:
                nlcClassification = json.loads(output)
            except:
                print ('Command:')
                print (curl_cmd)
                print ('Response:')
                print (output)
            nlc = {}
            if nlcClassification['classes'] > 0:
                nlc['text'] = text
                nlc['class'] = nlcClassification['classes'][0]['class_name']
                nlc['confidence'] = nlcClassification['classes'][0]['confidence']
                intents.append(nlc)
        newClassification['Intents'] = intents

        #allMessages.append(newClassification)

        #deciding which messages will in fact trigger an action
        """
        if newClassification['Sentiment'] is not "neutral":
            if newClassification['Action']['confidence'] > 0.90:
                return newClassification
        return "no_action"
        """
        if "true" in store:
            return newClassification
        else:
            return self.postProcessor(newClassification)
    def postProcessor(self,response):
        action = {}
        intents = Set()
        actionIntentNames = ""
        botIntentNames = ""
        urls = ""
        numberIntents = 0
        actionIntents = Set()
        botIntents = Set()
        answer = ""
        intentName = ""
        if len(response['Intents']) > 1:
            # complex scenario
            for intent in response['Intents']:
                intentName = intent['class']
                intents.add(intentName)
                if ("box" in intentName) or ("badge" in intentName) or ("enterprise" in intentName) \
                    or ("travel" in intentName) or ("expenses" in intentName):
                    actionIntents.add(intentName)
                elif ("task" in intentName) or ("repository" in intentName) or ("scheduling" in intentName) or ("analytics" in intentName):
                    botIntents.add(intentName)
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
            answer = "I can help you right away with " + actionIntentNames + ". Just follow the link(s): " + urls
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
            if len(botIntents) > 1:
                answer = answer+" and for "+botIntentNames+" I found these cool Bots that can help "+ urls
            else:
                answer = answer+" and for "+botIntentNames+" I found this Bot that can help you "+ urls
            action['Message'] = answer
        else:
            intent = response['Intents'][0]
            intent = intent['class']
            messages = ["If I understand you correctly, you need help with ",
                        "O.k. let's get you in better shape! It looks like you need help with ",
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
            if ("box" in intent) or ("badge" in intent) or ("enterprise" in intent) or ("travel" in intent) or ("expenses" in intent):
                action['Message'] = actionMessage[random.randint(0, len(actionMessage) - 1)] + url.encode('ascii', 'ignore').decode('ascii')
            else:
                action['Message'] = messages[random.randint(0, len(messages) - 1)] + intent + ". " + botMessage[
                    random.randint(0, len(botMessage) - 1)] + url.encode('ascii', 'ignore').decode('ascii')
        return action['Message']

    def getUrl(self,intent):
        if intent == 'task_management':
            url = "http://howdy.ai/?ref=slackappstore"
        elif intent == 'repository':
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
        else:
            url = None
        return url
