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

from watson.services import Services

services = Services()


# Top level orchestrator logic to invoke multiple services

class ClassifyMessage:


    def classifyText(self, text, store):

        response = {}
        clauses = []

        #Invoke Relation Extraction
        services.reService(text)

        # Identify simple versus multiple intents by analyzing the message using outut from Relation Extraction
        response, clauses = services.getClauses(response, clauses, text)

        #get the sentiment of the message from Alchemy services
        response = services.getAlchemySentiment(response, text)

        #get the keywords with sentiment from the message from Alchemy services
        response, searchChannels = services.getAlchemyKeywords(response, text)

        #classify the intent of the different clausess
        response, confidence = services.getIntents(response, clauses, searchChannels)

        # Is set to true, allows for the raw outputs from Watson services to be stored
        if "true" in store:
            return response
        else:            
            return services.postProcessor(response, confidence)

