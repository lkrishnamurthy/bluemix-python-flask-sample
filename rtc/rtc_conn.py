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
'''   # it's one we've already seen THIS session
Created on Mar 3, 2014

@author: mstave
'''
import sqlite3 as slite
import time
import random
import traceback
import json
import marshal
import logging
from os.path import os
import threading
import pdb

try:
    # noinspection PyUnresolvedReferences
    import requests
except ImportError:
    print '''
    ERROR: This program needs the python requests package
        (www.python-requests.org)
    For most versions of Python on a single-user system, use
    'pip install requests' or 'easy_install requests'
    '''
    exit()


class RtcConnection(object):
    '''
    Connect to Rational Team Concert Server via REST API
    '''

    def __init__(self, user, password, rtc_url, **kwargs):

        # required params

        self.user = user
        self.password = password
        self.rtc_base_url = rtc_url  # base URL

        # optional params from kwargs

        self.use_db = True  # use database or marshaled dict
        self.ignore_cache = False  # fetch all new values
        self.bad_urls = []  # ignore these URLs, typically due to RTC bug
                            # sometimes values are missing (404)
        self.db_file_name = "rest.db"  # name of sqllite use_db file on disk
        self.logged_in = False  # authenticated with RTC yet?

        self.__dict__.update(kwargs)

        # internal data

        self._new_cache = {}  # items added this _session
        self.is_dirty = False  # has data been changed?
        self._downloads_active = []  # URLs currently being fetched
        self._thread_data = None  # used to help be reentrant
        self._mem_cache = None  # in memory cache of REST data
        self._connection = None  # sqllite _connection

        self._adapter = requests.adapters.HTTPAdapter(
            pool_connections=50, pool_maxsize=200000)
        self._adapter.max_retries = 20
        self._session = requests.session()

        self._session.mount("https://", self._adapter)
        self._session.mount("http://", self._adapter)

    def init_cache(self):
        """
        Load the saved cache from disk
        Either db, or in-memory version
        Saves url : response(json) pairs
        """
        if self.use_db and self._connection is None:
            self._connection = slite.connect(
                self.db_file_name, check_same_thread=False)
            cur = self._connection.cursor()
            create_str = "create table if not exists rest(" \
                         "Uri TEXT PRIMARY KEY, data TEXT)"
            cur.execute(create_str)
            self._connection.commit()
            logging.info("Connected to %s", self.db_file_name)
            return

        if len(self._mem_cache) > 0:    # it's already loaded
            return

        try:
            logging.info("Reading stored cache [%s] ...", self.db_file_name)
            start_time = time.time()
            file_info = os.stat(self.db_file_name)
            self._mem_cache = marshal.load(open(self.db_file_name, "rb"))
            logging.info(
                "... Read complete, %d entries (%d MB) loaded in %d seconds",
                len(self._mem_cache), file_info.st_size / 1024 / 1024,
                time.time() - start_time)
        except OSError:
            logging.info("No cache found")
            self._mem_cache = {}

    def writeback_cache(self):
        '''
        Update the data on disk if it has changed
        '''

        if self.is_dirty:
            logging.info("Updating saved data")
            size = None
            if self.use_db:
                # size = len(self._new_cache)
                size = self.db_update()
            else:
                size = len(self._mem_cache)
                marshal.dump(self._mem_cache,
                             open(self.db_file_name, "wb"))
            logging.info("Write Complete, %d values written", size)
            self.is_dirty = False

    def db_update(self):
        ''' handle update of database
            returns how many rows written
        '''

        if self._new_cache is None or (len(self._new_cache) == 0):
            return
        str_ver = []
        for k in self._new_cache:
            str_ver.append((k, json.dumps(self._new_cache[k])))
        ret = self._connection.executemany(     # faster than one at a time
            "insert or replace into rest values (?,?)", str_ver)
        logging.info("Wrote %d new items", ret.rowcount)
        self._connection.commit()
        self._new_cache = {}
        return ret.rowcount

    def get(self, url, query_parms=None, headers=None):
        '''
        get data from relative rtc url
        returned cached values as appropriate
        '''

        results = None
        full_url = '%s/%s' % (self.rtc_base_url, url)
        logging.debug("Downloading " + full_url)
        waited = False
        while full_url in self._downloads_active:
            # don't try and download again if another request is already
            # in progress for the same URL
            waited = True
            logging.debug("waiting on duplicate download for %s", full_url)
            time.sleep(2 * random.random())
            # keep waiting until it's no longer on the list
        if waited:      # we waited, it should be in the cache
            cache_loc = '%s/%s' % (url, query_parms)
            while results is None:
                results = self.get_cached(cache_loc)
                if results is None:  # may take a bit for post-processing
                    time.sleep(2 * random.random())
                logging.debug("Sleeping waiting to get %s from cache",
                              cache_loc)
            return results
        else:
            self._downloads_active.append(full_url)
            self._session.head(full_url,allow_redirects=True)
            results = self._session.get(full_url, params=query_parms,
                                       verify=False, headers=headers)
            self._downloads_active.remove(full_url)
            return results

    def get_json(self, url, parms=None, headers=None):
        """
        Get RTC formatted JSON from RTC Server
        Check cache 1st
        Update cache if data is new
        """
        raw_content = None
        logging.debug("Getting %s with parms = %s and headers = %s",
                      url, parms, headers)
        cache_loc = '%s/%s' % (url, parms)  # , urllib.urlencode(parms))

        if url in self.bad_urls:
            return None
        mem = self.get_cached(cache_loc)
        if mem:
            return mem
        logging.debug("Need to download %s which wasn't in cache", url)
        if not self.logged_in:
            self.login()
        # noinspection PyBroadException
        try:
            raw_content = self.get(url, parms, headers)
            if raw_content is None:
                return None
            if type(raw_content) is not requests.Response:
                return raw_content
            # could but this check in get() but we don't want to update cache
            if raw_content.status_code == 404:
                traceback.print_stack()
                traceback.print_exc()
                
                logging.warning("HTTP 404 (Not found) was returned for %s",
                                url)
#                 pdb.set_trace()
                exit()
                return " "  # could set content = "" to prevent further attempt
            if raw_content.status_code != 200:
                raise RuntimeError("Error, status code %d received from %s" %
                                   (raw_content.status_code, url))
        except:  # exception from get()
            # sometimes the API returns an error when overloaded
            traceback.print_stack()
            logging.exception("retrying %s, 1st time was %s", url,
                              str(raw_content))
            time.sleep(random.random() * 10)
            if not self.logged_in:
                self.login()
            raw_content = self.get(url, parms, headers)
            if raw_content.status_code == 200:
                logging.info("retry of %s succeeded", url)
            else:
                raise RuntimeError("second error attempting to get %s, exiting"
                                   % (url))
        try:
            content = raw_content.json()
        except ValueError:  # can't always be converted
            content = raw_content.text
        if len(content) == 0:
            content = " "  # store something so we don't try again
        if self.use_db:
            self._new_cache[cache_loc] = content
        else:
            self._mem_cache[cache_loc] = content
        # build results are volatile, new stuff can get added..
        # we want to cache them for this run so we don't keep checking
        # during this run, but not to cache them for subsequent ones
        if 'resource/virtual/build/results' != cache_loc:
            logging.debug(
                'Adding to mem cache new value of length %d as %s',
                len(content), cache_loc)
            self.is_dirty = True
        return content

    def post(self, url, data):
        ''' used for updating, logging in, etc '''
        headers = {"Content-Type": "application/json"}
        return self._session.post('%s/%s' % (self.rtc_base_url, url), data, headers)

    def set_skip_cache_thread(self, truefalse):
        '''
        pull fresh data from RTC rather than from the cache/db
        for just this thread
        '''
        self.set_thread_data("skip_cache", truefalse)

    def get_skip_cache_thread(self):
        ''' see above '''
        return self.get_thread_data("skip_cache")

    def get_cached(self, full_uri):
        ''' pull saved version of URI instead of asking RTC for it '''

        # have we seen it in this session?
        mem = self._new_cache.get(full_uri, None)
        # for some things we skip the cache for just one thread
        # like when we want to re-check if a build has new results
        # but not re-get all the results from that build
        # that we've previously downloaded.
        if not mem and not self.get_skip_cache_thread() \
                 and not self.ignore_cache:
            if self.use_db:
                mem = self.db_get(full_uri)
            else:   # using memory cache, (marshaled from disk) not db
                mem = self._mem_cache.get(full_uri, None)
            logging.debug('Got result from location %s in cache', full_uri)
        return mem

    def set_thread_data(self, key, val):
        ''' store thread-specific info '''
        if self._thread_data is None:
            self._thread_data = threading.local()
        try:
            self._thread_data.data_dict[key] = val
        except AttributeError:
            self._thread_data.data_dict = {key: val}

    def get_thread_data(self, key):
        ''' read thread-specific info
            currently used for having different threads have
            different rules about using a cache
        '''
        if self._thread_data is None or \
            self._thread_data.__dict__.get('data_dict', None) is None:
            return None
        return self._thread_data.data_dict[key]

    def db_get(self, uri):
        ''' get value from sqllite '''
        logging.debug("checking use_db for %s", uri)
        res = self._connection.execute(
            "select data from rest where Uri=?", (uri,)).fetchone()
        if not res:
            return None
        logging.debug("use_db found value for %s", uri)
        return json.loads(res[0])

    def db_put(self, uri, data):
        '''
         write back one item to sqllite
        this isn't being used as we do db_update() to write all the new
        items en masse
        '''

        self._connection.execute(
             "insert or replace into rest (Uri,data) values (?,?)",
             (uri, data))
        self._connection.commit()

    def login(self):
        """
        Authenticate with RTC server

        """

        auth_err_msg = '''
        Error: No username set.  Use -U <rtc username> -P <rtc password>
        or env vars RTC_USER RTC_PASS"
        '''
        if not self.user:
            logging.error(auth_err_msg)
            exit()

        logging.debug("Logging in")
        self.get('authenticated/identity')
        retval = self.post('j_security_check', {'j_username': self.user,
                                                 'j_password': self.password})
        logging.debug('checking headers')
        logging.debug('Authentication headers: ' + str(retval.headers))
        if not retval.headers.get("x-com-ibm-team-repository-web-auth-msg",
                                  None):
            self.logged_in = True
        else:
            logging.error(
                "Failed to login to %s/%s with user:%s, password:%s\n" +
                auth_err_msg,
                self.rtc_base_url, "j_security_check", self.user,
                self.password)
            exit()
        logging.debug("Login complete")

