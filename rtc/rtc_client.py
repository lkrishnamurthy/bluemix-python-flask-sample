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
#!/usr/bin/python
#pylint: disable=E1103,C0301
#IGNORE E501

import logging
import re
import signal
import sys
import threading
import json
import subprocess
import shlex


import rtc_conn

##########################################################################
#
# rtc_client - a class that handles core RTC/Jazz operations
#
# This class contains the session to the RTC repository that you want to
# access.  Typically this is run as a main, and then methods are called
# to perform operations on the repository.
#
######################################
# REPOSITORY ACCESS:
#
# login - def login (self, userarg=None, pwarg=None, uriarg=None):
#                    Logs into access the Jazz instance for this object/session
#                    If no parameters are provided, it uses the previously set
#                    values for URI, username and password.
#
# set_jazzuri - def set_jazzuri (self, jazzuri):
#                    Sets the base URI that is used to access the Jazz instance
#
# set_userid -     def set_userid (self, userid):
#                    Sets the user ID that is used to access the Jazz instance
#
# set_passwd - def set_passwd (self, pw):
#                    Sets the user password that is used to access the Jazz instance
#
######################################
# RTC DATA METHODS:
#
# get_project_list - def get_project_list (self):
#                    Get a list of the valid projects for this user/repository
#
#
# get_workitem_by_id - def get_workitem_by_id(self, wi_id):
#                    Get the raw json for a work item, given the work item ID
#
######################################
# DATA ACCESS:
#
# get_oslc - def get_oslc(self, uri, params=None):
#                    Get data via an oslc request, passed in uri as a string, with
#                    any additional parameters needed.  Returns raw json as a default.
#
######################################
# INPUT/OUTPUT:
#
#
# iprint - def iprint(self, msg):
#                    Simple utility to output msg to either a log or an HTML file
#
#
# iprintline - def iprintline(self, msg):
#                    Simple utility to output msg followed by a linefeed to either
#                    a log or an HTML file
#
######################################
# INTERNAL METHODS:
#
# init_logging - def init_logging(self):
#                    Sets up the logging parameters which are used to log
#                    information which is stored in the logging file or
#                    sent to the terminal.
#
# flush_html - def flush_html(self):
#                    Returns the HTML string which is currently being built,
#                    and clears the HTML buffer to begin the next HTML string.
#                    Typically invoked when you have compiled all of your
#                    results in HTML, and now want to output those results.
#
#
# set_catalog - def set_catalog (self):
#                    Get the catalog for this repository and save it
#
#
##########################################################################

# If you do not have IPython installed in your base Python environment,
# you can install it by doing:
#      sudo pip install IPython
# (you may or may not need sudo depending on your setup)

sys.setrecursionlimit(14000)

class rtc_client(object):
    '''
    Class rtc_client
   '''
    log_class_init = None


    MAX_THREADS = 7     #  for HTTP requests fro RTC REST API
#
# __init__ - initialization routine
#

    def __init__(self, cmds=None):
        self.split_re = re.compile("[^a-zA-z]")  # used in split_segments


       # used to manage multiple threads
        self.worker_threads = []

        # build up a string of HTML output
        self.html_out = ""

        # for parsing command-line
        self.args = None
        self.options = None
        self.parser = None

        # set up logging
        self.log_file_name = 'outRTC.log'
        self.init_logging()

        if threading.currentThread().getName() == 'MainThread':
            signal.signal(signal.SIGINT, self.sigint_handler)
        else:
            logging.debug("Thread = " +
                          str(threading.currentThread().getName()))
        #
        # Define login credentials
        #
        self.user = "psmoraes@us.ibm.com"
        self.password = "40deu442be"
        self.rtc_url = '<RTC_URL>'  # default to override
        #self.jazz_url = 'https://jazzop09.rtp.raleigh.ibm.com:9943/jazz'
        self.jazz_url = 'https://hub.jazz.net/ccm34/'

        #
        # Define key pieces of information
        #
        self.catalog = None
        self.rtc_project_area = None
        self.rtc_conn = None

        # self login
        self.login(self.user, self.password)
#
# __del__ - Class destructor
#

    def __del__(self):
        if 'logging' in vars() and logging:
            logging.shutdown()
#
# sigint_handler - used to trap ctrl-c and do an orderly cleanup
#
    # noinspection PyUnusedLocal
    def sigint_handler(self, signum, frame):
# pylint: disable=W0613
        """
        Used to trap ctrl-c
        make sure dirty cache is written back
        referenced in __init__()

        :param signum:
        :param frame:
        :raise: RuntimeError
        """
        logging.exception('Handling caught SIGINT, cleaning up')
        # traceback.print_exc(file=sys.stdout)
        if self.rtc_conn is not None and self.rtc_conn.is_dirty:  # don't save bogus data
            self.__del__()
        raise RuntimeError
##################
#
# INTERNAL METHODS
#
##################
#
# init_logging - Sets up the logging parameters which are used to do
#                loginng information which is stored in the logging
#                file (outRTC.log by default) or sent to the terminal.
#
# ex. self.init_logging()
#
    def init_logging(self):

        if rtc_client.log_class_init:
            return
        rtc_client.log_class_init = True  # all instances share a logger
        for hnd in logging.root.handlers:  # helps in IDEs, iPython, etc.
            logging.root.removeHandler(hnd)
        logging.basicConfig(
            level=logging.INFO, filename=self.log_file_name, filemode="w")
        console = logging.StreamHandler()
        #
        # Toggle these lines if you want to see debug information
        #
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)

#
# set_catalog - Get the catalog for this repository and save it
#
# ex self.set_catalog()
#
    def set_catalog (self):
        #
        # Build the catalog URI
        #
        rtc_catalog_uri = self.jazz_url + '/oslc/workitems/catalog'
        #
        # Do an OSLC fetch of the catalog
        #
        #self.rtc_catalog = self.get_oslc(rtc_catalog_uri)

        return True

##################
#
# TECH DEBT
#
##################



#
# get_paged - Some RTC APIs return only one page of data at a time.
#             This concatentates them.  Used for
#

    def get_paged(self, uri, params=None):
        """
        Some RTC APIs return only one page of data at a time.
        This concatentates them
        """
        logging.debug("Getting paged URI " + uri)
        temp = self.get_oslc(uri, params)
        if type(temp) is not dict:
            return []
        result_name = u'oslc:results'
        # pylint disable=E1103
        if result_name not in temp.keys():
            result_name = u'oslc_cm:results'

        if u'oslc_cm:next' in temp.keys():
            return temp[result_name] + self.get_paged(temp[u'oslc_cm:next'])
        else:
            return temp[result_name]
#
# get_iteration - returns the current iteration, assuming that you have
#                 set a project and timeline for this session
#

    # def get_iteration(self, iter):
    #
    #     """
    #
    #     :param iter:
    #     :return:
    #     """
    #     for i in self.get_paged("oslc/iterations/"):
    #         if iter in i[u'dc:identifier']:
    #             return i[u'rdf:resource']

    def saved_query(self, query_id):
        """
        for example:
        url = 'https://myJazz:8050/ccm/oslc/queries/_MLDgQcIXEeGwdeoJlN_peA/
        rtc_cm:results'
        query would be _MLDgQcIXEeGwdeoJlN_peA
        url = 'https://myJazz:8050/ccm/resource/itemOid/com.ibm.team.workitem.
        query.QueryDescriptor/_SUN5wLTYEeGwZOoJlN_peA'
        query would be _SUN5wLTYEeGwZOoJlN_peA

        :rtype : json
        """
        url = self.rtc_url + '/oslc/queries/' + \
            query_id + '/rtc_cm:results'
        self.rtc_conn.set_skip_cache_thread(True)
        # we want to re-execute query each time, don't get cached value
        logging.debug("getting saved query from " + url)
        res = self.get_oslc(url)
        self.rtc_conn.set_skip_cache_thread(False)
        return res

    def wi_query(self, query):
        """
        Query work items
        go to https://myJazzServer:8050/ccm/oslc/workitems/catalog to get
        oslc_disc:details for your project area

        see
        https://jazz.net/blog/index.php/2009/09/11/
        oslc-and-rational-team-concert/
        http://open-services.net/bin/view/Main/OslcSimpleQuerySyntaxV1

        :param query: e.g.: 'oslc.where=rtc_cm:plannedFor=
        "https://server:9443/ccm/oslc/iterations/_TdocNB8ZEeOwarTrFtCA6Q"'
        or oslc.where=rtc_cm:state="{closed}"&oslc.select=dcterms:identifier,
        dcterms:title,oslc_cm:status
        :return:
        """
        return self.get_paged('oslc/contexts/' +
                              self.rtc_project_area +
                              '/workitems', query)

    def do_rtc_query(self, desc, query, answers):
        '''
        This is used for multithreaded queries so that results
        can be put and read from a data structure in a
        threadsafe way

        :param desc:  A description of the query
        :param query: The saved query ID
        :param answers : A list to save results
        '''
        logging.debug("Starting query for " + query)
        answers.append((desc, self.saved_query(query)))
        logging.debug(query + " query complete.")

    def multi_query(self, input_list):
        """
        Execute RTC queries in separate threads, block until they complete,
        place results in supplied queue
        :param input_list:
        :rtype : list of answers
        :param input_list: list of (descriptive string, query results )
        """
        threads = []
        answers = []
        for (desc, query) in input_list:
            threads.append(
                threading.Thread(target=self.do_rtc_query,
                                 args=((desc, query, answers))))
        for thr in threads:
            thr.start()
        for thr in threads:
            thr.join()
        return answers


    def multi_parse_wi(self, results):
        """
        Multi-threaded work item parsing
        :param results:
        :return:
        """
        threads = []
        answers = []
        for item in results:
            threads.append(
                threading.Thread(target=self.parse_wi_list,
                                 args=((item, answers))))
        for thr in threads:
            self.worker_threads.append(thr)
            thr.start()
            if len(self.worker_threads) > self.MAX_THREADS:
                self.catch_up()
        self.catch_up()
        return answers

    def get_wi_value(self, work_item, wival):
        """
        RTC stores different sorts of values differently...

        :param work_item: the work item
        :param wival: the type of work item
        :rtype : dict
        """
#        if not work_item.get(wival, None):
#            return None
        if u'dcterms:contributor' in wival:
            val = self.get_oslc(work_item[wival][u'rdf:resource'].
                                replace("jts", "ccm/oslc"))
        else:
            val = self.get_oslc(work_item[wival][u'rdf:resource'])
        if u'dcterms:contributor' in wival:
            return val[u'foaf:name']
        title = val.get(u'dc:title', None)
        if not title:
            title = val.get(u'dcterms:title', None)
        return title

    def parse_wi_list(self, work_items, answers):
        ''' helper for multithreaded query '''
        answers.append(self.parse_wi(work_items))

    def parse_wi(self, work_item):
        """
        Convert RTC formatted JSON to discrete variables
        :param work_item:
        :return:
        """
        try:
            priority = self.get_wi_value(work_item, u'oslc_cmx:priority')
            wi_type = self.get_wi_value(work_item, u'rtc_cm:type')
            status = (work_item[u'oslc_cm:status']).decode('utf-8')
            wi_id = str(work_item[u'dcterms:identifier'])
            url = str(work_item[u'rdf:about'])
            planned = self.get_wi_value(work_item, u'rtc_cm:plannedFor')
            if not planned:
                planned = "[unassigned]"
            state = self.get_wi_value(work_item, u'rtc_cm:state')
            team = self.get_wi_value(work_item, u'rtc_cm:teamArea')
            filedagainst = self.get_wi_value(work_item, u'rtc_cm:teamArea')
            title = work_item[u'dcterms:title']
#            contributor = self.get_wi_value(work_item, u'dcterms:contributor')
            severity = self.get_wi_value(work_item, u'oslc_cmx:severity')

        except UnicodeError:
            logging.error("error parsing " + str(work_item), exc_info=True)
            exit()
        # noinspection PyUnboundLocalVariable
        return {
            'priority': priority,
            'status': status,
            'state': state,
            'type': wi_type,
            'planned': planned,
            'id': wi_id,
            'url': url,
            'team': team,
            'filedagainst': filedagainst,
#            'contributor': contributor,
            'severity': severity,
            'title': title}
        return


#####################
#
# DATA ACCESS METHODS
#
#####################
#
# get_oslc - get data via an oslc request, passed in as a string with parameters
#
# ex: answer = self.get_oslc(self.rtc_catalog)
#
    def get_oslc(self, uri, params=None):
        '''
        see
        http://www.ibm.com/developerworks/rational/library/
        rational-team-concert-oslc/index.html?ca=drs
        for info on RTC and oslc
        '''
        # Check for a valid URI
        if not uri:
            return None
        logging.debug("request for oslc: " + uri)
        # Manipulate URI for request
        uri = uri.replace(self.jazz_url + "/", "")
        logging.debug("will request remove " + self.jazz_url + " to get " + uri)
        # Check for additional parameters on the request
        if not params:
            params = {}
        # Set the OSLC Core Version as 2.0 in the parameters
        # params["OSLC-Core-Version"] = "2.0"
        # Make the REST call, get data back in json format

        headers = {}
        headers["Content-Type"] = "application/json"
        headers["OSLC-Core-Version"] = "2.0"
        headers["Location"] = "https://hub.jazz.net"
        answer = self.session.get_json(
            uri, params, headers)
        return answer

#####################
#
# RTC DATA METHODS
#
#####################
#
# get_project_list - Get a list of the valid projects for this user/repository
#
    def get_project_list (self):
        #
        # Parse the catalog json for the list of projects
        #

        rtc_catalog_uri = self.jazz_url + '/oslc/workitems/catalog'

        self.rtc_catalog = self.get_oslc(rtc_catalog_uri)

        return self.rtc_catalog
#
# get_workitem_by_id - get the raw json for a work item, given the work item ID
#
# ex: my_wi = get_workitem(id)
#
    def get_workitem_by_id(self, wi_id):
        # Check for a valid work item id
        if not wi_id:
            return None
        logging.debug("request for work item by ID: " + wi_id)
        # Manipulate URI for request
        uri = self.jazz_url + "/resource/itemName/com.ibm.team.workitem.WorkItem/" + wi_id
        logging.debug("will request remove " + self.jazz_url + " to get " + uri)
        # do oslc call to get data
        answer = self.get_oslc(uri)
        return answer

###########################
#
# REPOSITORY ACCESS METHODS
#
###########################
#
# set_jazzuri - Sets the base URI that is used to access the Jazz instance
#
# ex: session.set_jazzuri('https://fully.qualified.domain.name:9445/rtc')
#
    def set_jazzuri (self, jazzuri):
        self.jazz_url = jazzuri
        return True

#
# set_userid - Sets the user ID that is used to access the Jazz instance
#
# ex: session.set_userid('dtoczala@acme.org')
#
    def set_userid (self, userid):
        self.user = userid
        return True

#
# set_passwd - Sets the user password that is used to access the Jazz instance
#
# ex: session.set_passwd('mybiglongpassword')
#
    def set_passwd (self, pw):
        self.password = pw
        return True

#
# login - Logs into access the Jazz instance for this object/session
#         If no parameters are provided, it uses the previously set
#         values for URI, username and password.
#
# Ex: session.login('userid','password','https://fully.qualified.domain.name:9445/rtc')
#
    def login (self, userarg=None, pwarg=None, uriarg=None):
        #
        # If values for user, password or base URI are specified, then use
        # those values.  Otherwise use the session values
        #
        if userarg == None:
            userarg = self.user
        if pwarg == None:
            pwarg = self.password
        if uriarg == None:
            uriarg = self.jazz_url
        #
        # Log into the RTC instance indicated
        #
        try:
            self.session = rtc_conn.RtcConnection(userarg,
                                                  pwarg,
                                                  uriarg)
        except:
           print("Login credentials did not authenticate.\n")

        try:
            self.session.login()
            print("Login succeeded\n")
        except:
           print("Login credentials did not authenticate.\n")

        #
        # Retrieve and setup common information
        #
        self.session.db_file = 'rest.db'
        self.session.init_cache()
        self.set_catalog()

        return True

    def post_oslc(self, uri, data=None):

        # Check for a valid URI
        if not uri:
            return None
        logging.debug("request for oslc: " + uri)
        # Manipulate URI for request
        uri = uri.replace(self.jazz_url + "/", "")
        logging.debug("will request remove " + self.jazz_url + " to get " + uri)
        # Make the REST call, get data back in json format
        answer = self.session.post(uri, data)

        return answer

    def create_work_item(self, title, summary, type=None):

        project_id = "-gmJUWbeEeWUoNiz2-ZOFQ"
        uri = self.jazz_url + "/oslc/contexts/" + project_id + "/workitems"
        typeTask = self.jazz_url + "/oslc/types/" + project_id + "/task"
        typeCategory = self.jazz_url + "/resource/itemOid/com.ibm.team.workitem.Category/_33eQGbeEeWUoNiz2-ZOFQ"
        data = json.dumps({'dc:title': title, 'dc:description': summary, 'dc:type': { 'rdf:resource': typeTask},'rtc_cm:filedAgainst':{'rdf:resource': typeCategory}})
        return self.post_oslc(uri,data)

    def get_work_item_status(self, work_item_id):

        #work_item = self.get_workitem_by_id(work_item_id)
        #return work_item

         request = self.jazz_url + "resource/itemName/com.ibm.team.workitem.WorkItem/"+work_item_id
         credentials = self.user + ":" + self.password
         curl_cmd = 'curl %s -H "Accept:application/json" -L -i -H "OSLC-Core-Version:2.0" -u %s' % (request,credentials)
         process = subprocess.Popen(shlex.split(curl_cmd), stdout=subprocess.PIPE)
         output = process.communicate()[0]
         work_item_status = {}
         try:
             searchString = '"oslc_cm:status":"'
             searchStringEnd = '"rtc_cm:resolvedBy"'
             pos = re.search(searchString,output)
             start = pos.start()
             endpos = re.search(searchStringEnd,output)
             end = endpos.start() - 2
             status = output[start+len(searchString):end]
             if status is not None:
                 work_item_status['status'] = status.strip()
             else:
                 work_item_status['status'] = "Status not found or not yet created"

             searchDescription ='"dcterms:title":"'
             searchDescriptionEnd = '"rtc_cm:com.ibm.team.workitem.linktype.attachment.attachment":'
             pos1 = re.search(searchDescription,output)
             startDes = pos1.start()
             endPos1 = re.search(searchDescriptionEnd,output)
             endDes = endPos1.start()-2
             desc = output[startDes+len(searchDescription):endDes]

             if desc is not None:
                 work_item_status['description'] = desc.strip()
             else:
                 work_item_status['description'] = ""
         except:
             print ('Command:')
             print (curl_cmd)
             print ('Response:')
             print (output)
             return None

         if work_item_status is None:
             return None
         else:
             return work_item_status


def main():
 # ''' cli '''
    client = rtc_client()
    #client.execute()
    #client.rtc_conn.writeback_cache()
    #if client.login("l.krishna@us.ibm.com","M4nuS3ti16"):
    #    print ("Authentication Succeeded")
    #else:
    #    print ("Authentication Failed")

    #print(client.get_project_list())

    # work_item = client.get_workitem_by_id("15357")
    # if work_item is None:
    #      print("Work item cannot be found")
    # else:
    #      print(work_item)
    #      print(client.parse_wi(work_item).get("type") + ":" + client.parse_wi(work_item).get("title") + client.parse_wi(work_item).get("status") + " is created")

    print("Status : %s" % client.get_work_item_status("1205"))


    #print("Status : %s" % client.get_work_item_status("15388"))

    #new_work_item = client.create_work_item("Dummy from LK","Dummy Desc from LK")
    #if new_work_item is not None:
    # print(client.parse_wi(new_work_item).get("type") + ":" + client.parse_wi(new_work_item).get("title") + " is created")

if __name__ == '__main__':
    main()
