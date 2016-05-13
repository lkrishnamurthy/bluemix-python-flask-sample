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
Created on May 10 2016

@author: lkrishnamurthy
"""
from cloudant.client import Cloudant
from cloudant.query import Query
from cloudant.result import Result


class CloudantHelper:
    COUCHDB_USER = ""
    COUCHDB_PASSWORD = ""
    COUCHDB_URL = ""

    dbclient = None

    def __init__(self, userid, password, url):
        self.init(userid, password, url)
        pass

    def init(self, userid, password, url):
        self.COUCHDB_URL = url
        self.COUCHDB_USER = userid
        self.COUCHDB_PASSWORD = password

        print("Connecting to Cloudant..")
        self.dbclient = Cloudant(self.COUCHDB_USER, self.COUCHDB_PASSWORD, url=self.COUCHDB_URL)

        # Connect to the server
        self.dbclient.connect()
        print("Connected to Cloudant!")

    def query(self, database=None, selectorField=None, value=None):

        if self.dbclient is None:
            self.dbclient.connect()

        db = self.dbclient[database]
        query = Query(db)
        if query is not None:
            with query.custom_result(selector={selectorField: value}) as res:
                if res is not None:
                    return res[0]
                else:
                    return None
        else:
            return None

    def queryAll(self, database=None, field=None, value=None):
        resultsArray = []
        if self.dbclient is None:
            self.dbclient.connect()

        db = self.dbclient[database]
        result_collection = Result(db.all_docs, include_docs=True)

        count = 0
        for result in result_collection:
            if result['doc'] is not None:
                if field in result['doc'] and result['doc'][field] == value:
                    resultsArray.append(result['doc'])
                    count += 1
        return resultsArray

    def disconnect(self):
        # Disconnect from the server
        if self.dbclient is not None:
            self.dbclient.disconnect()
            print("Disconnected from Cloudant.")


def main():
    COUCHDB_USER = "c36550aa-523c-46b7-b4a7-5314df97087e-bluemix"
    COUCHDB_PASSWORD = "73ef275e1f46d75ee425e4c10ae2f1a49ed0b45b3ca5e8fe5f7a38d585cee26f"
    COUCHDB_URL = "http://c36550aa-523c-46b7-b4a7-5314df97087e-bluemix.cloudant.com"

    helper = CloudantHelper(COUCHDB_USER, COUCHDB_PASSWORD, COUCHDB_URL)

    if helper is not None:
        print("Query All\n")
        print helper.queryAll('classifierdb', field='status', value='A')
        print("\n")
        print("Query Single Row\n")
        print helper.query('classifierdb', selectorField='status', value='I')[0]['classifierId']
        print helper.query('actions',selectorField='intent',value='enterprise_directory')
        helper.disconnect()


if __name__ == '__main__':
    main()
