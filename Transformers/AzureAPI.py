import os
import requests
import datetime
import base64
import uuid
import hashlib
import hmac
import sys
import re

from io import StringIO, BytesIO
from collections import OrderedDict
from xml.etree import ElementTree


PUT_BLOB_LIMIT = 1024 * 1024 * 64      # 64 MB
PUT_BLOCK_CHUNK_SIZE = 1024 * 1024 * 4 # 4 MB
AZ_VERSION = '2015-02-21'


class AzureException(Exception):
    """ Base calss for azure exeptions """
    pass
    
class NoSuchContainerError(AzureException):
    def __init__(self, msg):
        super(NoSuchContainerError, self).__init__(msg)

class StdoutLogger(object):
    '''
    simple log class to mimic fme api
    '''
    def logMessageString(self, msg, level = 0):
        print(msg) # Py 3
    def logException(self, e, level = 0):
        self.logMessageString(str(e), level)
class AzureAPI(object):
    if sys.version_info < (3,):
        from collections import Iterable
        _unicode_type = unicode
    else:
        from collections.abc import Iterable # TODO: this code was found somewhere but its logic is not clear to me... 
        _unicode_type = str
    def __init__(self, account, secret, logfile = StdoutLogger(), logprefix = '', loglevel = 0):
        self.logfile = logfile 
        self.logprefix = logprefix
        self.loglevel = loglevel
        self.account = account
        self.secret = secret
    def info(self, message):
        self.logfile.logMessageString('%s: %s' % (self.logprefix, message), self.loglevel)
    def append_block(self, container, blob_name, block_data):
        headers = AzureAPI._create_headers(block_data)
        url = 'https://%s.blob.core.windows.net/%s/%s?comp=appendblock' % (self.account, container, blob_name)
        self.info('Appending data to blob using url %s' % url)
        _string_to_sign = self._authorize(headers, container, blob_name, 'comp:appendblock')
        r = requests.put(url, headers=headers, data = block_data)
        if r.status_code != 201:
            self.info('ERROR status %s: `%s`' % (r.status_code, _string_to_sign))
            raise Exception(str(r.content))
    def put_block(self, container, blob_name, block_data):
        headers = AzureAPI._create_headers(block_data)
        headers['x-ms-blob-type'] = 'BlockBlob'
        block_id = AzureAPI._encode_base64(uuid.uuid4().hex)
        #https://myaccount.blob.core.windows.net/mycontainer/myblob?comp=block&blockid=id
        url = 'https://%s.blob.core.windows.net/%s/%s?comp=block&blockid=%s' % (self.account, container, blob_name, block_id)
        self.info('Uploading block of data to blob using url %s' % url)
        _string_to_sign = self._authorize(headers, container, blob_name, 'blockid:%s\ncomp:block' % block_id)
        r = requests.put(url, headers=headers, data=block_data)
        if r.status_code != 201: raise Exception(str(r.content))
        return block_id
    def put_block_list(self, container, blob_name, block_list, xtra_headers = {}):
        list_fragments = ''.join(map(lambda s: '<Uncommitted>{}</Uncommitted>'.format(s), block_list))
        data = '<?xml version="1.0" encoding="utf-8"?><BlockList>{}</BlockList>'.format(list_fragments)
        headers = AzureAPI._create_headers(data, xtra_headers)
        url = 'https://%s.blob.core.windows.net/%s/%s?comp=blocklist' % (self.account, container, blob_name)
        _string_to_sign = self._authorize(headers, container, blob_name, 'comp:blocklist')
        r = requests.put(url, headers=headers, data=data)
        if r.status_code != 201: raise Exception(str(r.content))
    def put_blob(self, container, blob_name, fin, xtra_headers = {}):
        fin.seek(0, os.SEEK_END)
        size = fin.tell()
        fin.seek(0, os.SEEK_SET)
        if size < PUT_BLOB_LIMIT:
            data = fin.read()
            headers = AzureAPI._create_headers(data, xtra_headers)
            headers['x-ms-blob-type'] = 'BlockBlob'
            _string_to_sign = self._authorize(headers, container, blob_name)
            #self.warn(_string_to_sign)
            url = 'https://%s.blob.core.windows.net/%s/%s' % (self.account, container, blob_name)
            self.info('Uploading data to blob using url %s' % url)
            r = requests.put(url, headers=headers, data=data)
            if r.status_code != 201: 
                if r.status_code == 404 and re.search('ContainerNotFound', str(r.content)) != None:
                    raise NoSuchContainerError('but_blob: ContainerNotFound')
                raise Exception(str(r.content))
            #if r.status_code != 201: raise Exception(str(r.content))
        else:
            ids = []
            for offset in range(0, size, PUT_BLOCK_CHUNK_SIZE):
                self.info('Uploading `%s`, %s%%' % (blob_name, int(round(offset * 100 / size)) ) )
                block_size = min(PUT_BLOCK_CHUNK_SIZE, size - offset)
                ids.append(self.put_block(container, blob_name, fin.read(block_size)))
            self.put_block_list(container, blob_name, ids, xtra_headers)
            #self.info('ID LIST COMMITTED: %s' % '\n\t'.join(ids))
        self.info('Done uploading %s bytes of data' % size)
    def list_blobs(self, container,prefix=None,delimiter='/',recursive=False):
        # https://myaccount.blob.core.windows.net/mycontainer?restype=container&comp=list
        headers = AzureAPI._create_headers()
        #CubeSourceDataFile/coast
        #
        params = {'delimiter' : delimiter, 'comp': 'list', 'restype': 'container'}
        if prefix: params['prefix'] = prefix
        params = OrderedDict(sorted(params.items(), key=lambda t: t[0]))
        querystring = '&'.join(map(lambda t: '{}={}'.format(*t), params.items()))
        querystringencoded = '\n'.join(map(lambda t: '{}:{}'.format(*t), params.items()))
        url = 'https://%s.blob.core.windows.net/%s?%s' % (self.account, container,querystring)
        _string_to_sign = self._authorize(headers, container, querystringencoded = querystringencoded, http_method = 'GET')
        #self.info(_string_to_sign)
        #self.info('Listing blobs using url %s' % url)
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            raise Exception(str(r.content))
        root = ElementTree.fromstring(r.content.decode('utf-8-sig'))
        for blobprefix in root.iter('BlobPrefix'):
            buf = BytesIO()
            ElementTree.ElementTree(blobprefix).write(buf, encoding='utf8', xml_declaration=False)
            yield 'BlobPrefix', prefix, buf.getvalue().decode('utf-8')
            if recursive:
                for returntype, used_prefix, blob in self.list_blobs(container, prefix=blobprefix.findtext('Name'), delimiter=delimiter,recursive=True):
                    yield returntype, used_prefix, blob
        for blob in root.iter('Blob'):
            buf = BytesIO()
            ElementTree.ElementTree(blob).write(buf, encoding='utf8', xml_declaration=False)
            yield 'Blob', prefix, buf.getvalue().decode('utf-8')
    def create_container(self, container):
        headers = AzureAPI._create_headers()
        headers['x-ms-blob-public-access'] = 'blob'
        url = 'https://%s.blob.core.windows.net/%s?restype=container' % (self.account, container)
        _string_to_sign = self._authorize(headers, container, querystringencoded = 'restype:container', http_method = 'PUT')
        self.info('Creating missing container %s' % container)
        r = requests.put(url, headers=headers)
        if r.status_code != 201:
            raise Exception(str(r.content))
        return r.content      
    def delete_container(self, container):
        headers = AzureAPI._create_headers()
        url = 'https://%s.blob.core.windows.net/%s?restype=container' % (self.account, container)
        _string_to_sign = self._authorize(headers, container, querystringencoded = 'restype:container', http_method = 'DELETE')
        self.info('Recycling container %s' % container)
        r = requests.delete(url, headers=headers)
        if r.status_code != 202:
            if r.status_code == 404 and re.search('ContainerNotFound', str(r.content)) != None:
                raise NoSuchContainerError('but_blob: ContainerNotFound')
            raise Exception(str(r.content))
        return r.content  
    def delete_blob(self, container, blob_name):
        headers = AzureAPI._create_headers()
        url = 'https://%s.blob.core.windows.net/%s/%s' % (self.account, container, blob_name)
        _string_to_sign = self._authorize(headers, container, blob_name = blob_name, http_method = 'DELETE')
        #self.info(_string_to_sign)
        self.info('Deleting blob using url %s' % url)
        r = requests.delete(url, headers=headers)
        if r.status_code != 202:
            raise Exception(str(r.content))
    def _authorize(self, headers, container_name, blob_name = None, querystringencoded = None, http_method = 'PUT'):
        content_length = ''
        if headers.get('Content-Length') != '0':
            content_length = headers.get('Content-Length')
        fields = [
                      http_method # VERB (http-method)
                    , '' # Content-Encoding
                    , '' # Content-Language
                    , content_length
                    , '' # Content-MD5
                    , headers.get('Date','') # Date
                    , '' # If-Modified-Since
                    , '' # If-None-Match
                    , '' # If-Unmodified-Since
                    , '' # Range
                    , '' # ?
                    , '' # ?
                    ]
        if headers.get('x-ms-blob-public-access', None): fields.append('x-ms-blob-public-access:%s' % headers.get('x-ms-blob-public-access'))
        if headers.get('x-ms-blob-type', None): fields.append('x-ms-blob-type:%s' % headers.get('x-ms-blob-type'))
        fields.append('x-ms-date:%s' % headers.get('x-ms-date'))
        fields.append('x-ms-version:%s' % headers.get('x-ms-version'))
        if blob_name:
            fields.append('/%s/%s/%s' % (self.account, container_name, blob_name))
        else:
            fields.append('/%s/%s' % (self.account, container_name))
        if querystringencoded: fields.append(querystringencoded)
        _string_to_sign = '\n'.join(fields)
        signature = AzureAPI._sign_string(self.secret , _string_to_sign)
        headers['Authorization'] = 'SharedKey %s:%s' % (self.account, signature)
        return _string_to_sign
    @staticmethod
    def _create_headers(data = '', xtra_headers={}):
        headers = {
                  'Content-Length': str(len(data))
                , 'x-ms-date': AzureAPI._httpdate(datetime.datetime.utcnow())
                , 'x-ms-version': AZ_VERSION
            }
        headers.update(xtra_headers)
        return OrderedDict(sorted(headers.items(), key=lambda t: t[0]))
    @staticmethod
    def _httpdate(dt):
        """Return a string representation of a date according to RFC 1123
        (HTTP/1.1).
    
        The supplied date must be in UTC.
    
        """
        weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
        month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                 "Oct", "Nov", "Dec"][dt.month - 1]
        return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dt.day, month,
            dt.year, dt.hour, dt.minute, dt.second)
    @staticmethod
    def _encode_base64(data):
        if isinstance(data, AzureAPI._unicode_type):
            data = data.encode('utf-8')
        encoded = base64.b64encode(data)
        return encoded.decode('utf-8')
    @staticmethod
    def _decode_base64_to_bytes(data):
        if isinstance(data, AzureAPI._unicode_type):
            data = data.encode('utf-8')
        return base64.b64decode(data)
    @staticmethod
    def _sign_string(key, string_to_sign, key_is_base64=True):
        if key_is_base64:
            key = AzureAPI._decode_base64_to_bytes(key)
        else:
            if isinstance(key, AzureAPI._unicode_type):
                key = key.encode('utf-8')
        if isinstance(string_to_sign, AzureAPI._unicode_type):
            string_to_sign = string_to_sign.encode('utf-8')
        signed_hmac_sha256 = hmac.HMAC(key, string_to_sign, hashlib.sha256)
        digest = signed_hmac_sha256.digest()
        encoded_digest = AzureAPI._encode_base64(digest)
        return encoded_digest