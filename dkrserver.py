#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" Exposes Docker run as an API """

import os
import socket
from pathlib import Path
import json
import logging
from logging.handlers import RotatingFileHandler
from wsgiref import simple_server

from yaml import safe_load

import docker

import falcon


def _getlgr(loglevel=logging.WARNING, logfname='', name='dkrapp'):
    """ Function provides a logger
    Parameters
    -----------
    loglevel : int
        Set the loglevel (default: WARNING)
    logfname : str
        Log file location (default: '<scriptdir>/dkrApiEngine.log')
    name : str
        Set the logger name (default: application.name)

    Returns
    -------
    loghandle : lgr object
        lgr for generating file output
    """
    if logfname == '':
        flpath = os.path.dirname(os.path.realpath(__file__))
        logfname = f"{flpath}/dkrApiEngine.log"
    lgr = logging.getLogger(name)
    lgr.setLevel(loglevel)
    if not lgr.handlers:
        flh = RotatingFileHandler(logfname,
                                  mode="a", maxBytes=5000000, #5MB files
                                  backupCount=3)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(funcName)s() %(message)s")
        flh.setFormatter(fmt)
        lgr.addHandler(flh)
        lgr.propagate = False
    return lgr

_LOGGER = _getlgr()


class CustomAdapter(logging.LoggerAdapter):
    ''' Customer Adapter to capture ip and username on log files'''
    def process(self, msg, kwargs):
        return f"{self.extra['username']} {self.extra['ip']} {msg}", kwargs


def _load_config(lgr):
    ''' Get defaults from the config file '''
    lgr.debug("Load config details from config file")
    with open('config.yml', 'r') as yml:
        cfg = safe_load(yml)
    return cfg

_CFG = _load_config(_LOGGER)

def _allmnts():
    ''' Get list of mounts for running CDP ML container '''
    def getmnt(src, tgt=None, ro=True):
        if tgt:
            mnt = docker.types.Mount(source=f"{src}", target=f"{tgt}", type="bind", read_only=ro)
        else:
            mnt = docker.types.Mount(source=f"{src}", target=f"{src}", type="bind", read_only=ro)
        return mnt

    mounts = []
    javahome = Path('/usr/bin/java').resolve()
    if javahome.is_file():
        java = '/'.join(javahome.parts[:-2])[1:]
        jshare = '/usr/share/java'
        mounts.append(getmnt(java))
        mounts.append(getmnt(jshare))
        javazi = Path('/usr/share/javazi-1.8')
        if javazi.is_dir():
            mounts.append(getmnt(javazi))

    cldr = Path('/opt/cloudera/parcels/CDH')
    if cldr.is_dir():
        mounts.append(getmnt(cldr))
        cldrfull = cldr.resolve()
        mounts.append(getmnt(cldrfull))
        for srvc in ("hadoop", "hive", "spark"):
            mounts.append(getmnt(f"/etc/{srvc}/conf"))
        sprk3 = Path('/opt/cloudera/parcels/SPARK3')
        if sprk3.is_dir():
            mounts.append(getmnt(sprk3))
            sprk3full = sprk3.resolve()
            mounts.append(getmnt(sprk3full))

    for fl in ('/etc/krb5.conf',  '/etc/ntp.conf'):
        flpath = Path(fl)
        if flpath.is_file():
            mounts.append(getmnt(flpath))
    return mounts

def _customlgr(func):
    ''' Set the lgr to custom logger, and with loglevel specified in the request.
        Once loglevel is set on a request, loglevel remains active on all future requests.
        To reset/change, set to another value in a future request
    '''
    def inner(self, req, resp):
        try:
            loglevel = req.context.doc.get('loglevel', None)
            self.lgr.warning(f"loglevel: {req.context.doc},  {loglevel}")
            if loglevel:
                if loglevel in (10, 20, 30, 40, 50):
                    self.lgr.setLevel(loglevel)
                elif loglevel.upper() in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
                    self.lgr.setLevel(loglevel.upper())
        except AttributeError:
            self.lgr.debug("No loglevel in body")
        except ValueError:
            self.lgr.warning(f"Incorrect loglevel in body: {loglevel}")
        self.username = req.get_header('username') # default is system user
        if self.username is None:
            self.lgr.warning("No Username in header")
            self.username = "system"
        self.lgr = CustomAdapter(_LOGGER, {'username': f"{self.username}",
                                            'ip': f"{req.access_route}"
                                          }
                                )
        return func(self, req, resp)
    return inner


class RequireJSON():
    '''Request message and method/verb validator '''
    def __init__(self, logger, cfg):
        self.lgr = logger
        self.config = cfg

    def process_request(self, req, resp):
        '''Validator method for JSON body and allowed verb '''
        self.lgr.warning(f"username header required: {self.config['HEADERTOKEN']}")
        if self.config['HEADERTOKEN']:
            uname = req.get_header('username')
            self.lgr.error(f"Request by {uname}")
            if uname is None:
                raise falcon.HTTPUnauthorized(
                    title='username required in header',
                    description="username required in request header"
                )
        if not req.client_accepts_json:
            self.lgr.error("Client doesn't accept JSON")
            raise falcon.HTTPNotAcceptable(
                title='DKR-RJ01: API supports JSON encoded responses only.',
                href='www.json.org')
        if req.method not in ('POST', 'GET', 'DELETE', 'OPTIONS', 'PUT'):
            self.lgr.error(f"Invalid request method:{req.method}")
            raise falcon.HTTPMethodNotAllowed(title="DKR-RJ02: Unsupported Method in API call",
                                              description='Trying to access unsupported Method.',
                                              allowed_methods=['POST', 'GET', 'DELETE'])
        if req.method in ('POST', 'GET') and 'application/json' not in req.content_type \
           and req.content_length not in (None, 0):
            self.lgr.error(f"Invalid request content type:{req.content_type}")
            raise falcon.HTTPUnsupportedMediaType(
                    title='DKR-RJ03: API supports JSON encoded requests only.',
                    href='www.json.org')

        if req.method in ('DELETE', 'PUT') and ('application/json' not in req.content_type \
                                                or req.content_length in (None, 0)):
            self.lgr.error(f"Invalid request content type:{req.content_type}")
            raise falcon.HTTPUnsupportedMediaType(
                    title='DKR-RJ04: API requires JSON encoded requests')

class JSONTranslator():
    '''Request JSON message validator '''
    def __init__(self, logger):
        self.lgr = logger

    def process_request(self, req, resp):
        '''Validator method for JSON document '''
        if req.content_length in (None, 0):
            return

        req.context.doc = req.media
        if not req.context.doc:
            self.lgr.info('Empty request Body')
        else:
            self.lgr.debug(f"Request body: {req.context.doc}")


    def process_response(self, req, resp, resource, req_succeeded):
        ''' convert result to a json document'''
        if not hasattr(resp.context, 'result'):
            return
        resp.text = json.dumps(resp.context.result)


class DkrInit():
    '''Initialize Docker, get list of running containers'''
    def __init__(self, logger, cfg):
        self.lgr = logger
        self.dflt_mnts = _allmnts()
        self.dkr = docker.from_env()
        self.config = cfg
        self.config['MAXCPU'] = float(self.config['MAXCPU'])
        self.config['host'] = socket.getfqdn()
        self.config['ip'] = socket.gethostbyname(self.config['host'])
        self.lgr.setLevel(self.config['LOGLEVEL'].upper())
        self.username = None

    def containers(self):
        ''' Get list of running containers '''
        self.dkr = docker.from_env()
        rundct = {}
        for each in self.dkr.containers.list(all=True):
            rundct[each.name] = [each.short_id, each.attrs]
        return rundct


class DkrImages(DkrInit):
    ''' Get list of available images'''

    @_customlgr
    def on_get(self, req, resp):
        ''' Get container details for the user '''
        lst = []
        self.lgr.info("received request for images list")
        for each in self.dkr.images.list():
            fsze = each.attrs['Size']/(1024*1024)
            dct = {'tags': each.tags,
                   'short id': each.short_id,
                   'size': f"{fsze:,.2f}MB",
                   'created': each.attrs['Created'] }
            lst.append(dct)
        self.lgr.debug(f"images list: {lst}")
        resp.context.result = {'Available Images': lst}
        resp.status = falcon.HTTP_200


class DkrLaunch(DkrInit):
    ''' Docker run, stop or get list of containers for a user'''

    def container_info(self, item):
        ''' select few container attributes '''
        dct = {'container name': item}
        # if the application exposes a port, show the app url
        port = 0
        container = self.dkr.containers.get(item)
        dkrattrs = container.attrs
        try:
            indx = dkrattrs['Args'].index('--port')
            port = dkrattrs['Args'][indx + 1]
        except ValueError:
            self.lgr.debug("No port specified on docker run cmd")
            # Get the values of network settings for exposedport
            try:
                for key, val in dkrattrs['NetworkSettings']['Ports'].items():
                    self.lgr.debug(f"key: {key}, value:{val}")
                    port = val[0]['HostPort']
                    break
            except (KeyError, TypeError):
                port = 0

        if port:
            dct['application url'] =  f"{self.config['host']}:{port}"
        dct['container id'] = container.short_id
        # Show select few container details
        msze = dkrattrs['HostConfig']['Memory']/(1024*1024)
        cpus = dkrattrs['HostConfig']['NanoCpus']/1000000000
        dct['container details'] = {'Status': dkrattrs['State']['Status'],
                                    'Created': dkrattrs['Created'],
                                    'StartedAt': dkrattrs['State']['StartedAt'],
                                    'Image': dkrattrs['Config']['Image'],
                                    'Memory': f"{msze:,.0f}MB",
                                    'Cpus': cpus,
                                    'Mounts': dkrattrs['Mounts']}
        return dct

    def _getcontainer(self, reqmsg):
        ''' Get the container object for start, stop or delete'''
        cname = None
        cid = None
        cntr = None
        self.lgr.debug(f"Request document {reqmsg}")
        try:
            cname = reqmsg['container name']
            self.lgr.debug(f"Container : {cname}")
        except (AttributeError, KeyError):
            self.lgr.debug("No container name specified")
            try:
                cid = reqmsg['container id']
                self.lgr.debug(f"Container id: {cid}")
            except (AttributeError, KeyError):
                self.lgr.debug("No container id specified")
        runningcs = self.containers()
        self.lgr.debug(f"Running containers {runningcs}")
        for each in runningcs :
            self.lgr.info(f"container Name:{each}  Id: {runningcs[each][0]}")
            # API short_id length can be lesser than what the user passes in the API, hence startswith
            if each.startswith(self.username):
                if each == cname or \
                   (cid and (cid.startswith(runningcs[each][0]) or
                             runningcs[each][0].startswith(cid)
                            )
                   ):
                    cntr = self.dkr.containers.get(each)
                    self.lgr.debug(f"Got container Name:{each}  Id: {runningcs[each][0]}")
                    break
        return cntr

    @_customlgr
    def on_get(self, req, resp):
        ''' Get list of user containers '''
        lst = []
        self.lgr.info("received request for containers list")
        for each in self.containers():
            self.lgr.debug(f"container name: {each}")
            if each.startswith(self.username):
                lst.append(self.container_info(each))
        self.lgr.debug(f"container list: {lst}")
        resp.context.result = {'Running Containers': lst}
        resp.status = falcon.HTTP_200

    @_customlgr
    def on_put(self, req, resp):
        ''' Perform start/stop/retart on user container '''
        try:
            action = req.context.doc['action']
            self.lgr.debug(f"Container action: {action}")
        except (AttributeError, KeyError):
            action = None
            self.lgr.debug("No action specified")
        else:
            container = self._getcontainer(req.context.doc)
        #Default message
        resp.context.result = {f"Action {action} failed":
                               f"Invalid action or invalid container or container doesn't belong to user {self.username}"}
        resp.status = falcon.HTTP_412
        if container and action and action.lower() in ('start', 'stop', 'restart'):
            try:
                if action.lower() == 'start':
                    container.start()
                elif action.lower() == 'stop':
                    container.stop()
                elif action.lower() == 'restart':
                    container.restart()
            except docker.errors.APIError as err:
                self.lgr.debug(f"failed to perform {action} due to {err}")
            else:
                # Get the updated container information
                container = self.dkr.containers.get(container.name)
                resp.context.result = {f"Action {action} successful": self.container_info(container.name)}
                resp.status = falcon.HTTP_200

    @_customlgr
    def on_delete(self, req, resp):
        ''' Remove/delete the user container '''
        container = self._getcontainer(req.context.doc)
        if container:
            container.remove(force=True)
            resp.context.result = {'Delete successful':
                                   f"Container name:{container.name}, id:{container.short_id}"}
            resp.status = falcon.HTTP_200
        else:
            resp.context.result = {'Delete failed':
                                   f"Invalid container or doesn't belong to user {self.username}"}
            resp.status = falcon.HTTP_412


    @_customlgr
    def on_post(self, req, resp):
        ''' Handler for launching containers '''
        post_dct = {}
        cmdlst = None

        # Container names are of the form user, user1...
        ulst = [each for each in self.containers() if each.startswith(self.username)]
        self.lgr.debug(f"User Container list: {ulst}")
        if len(ulst) >= self.config['MAX_PER_USER']:
            self.lgr.error("Will not launch new container, exceeds user limit")
            resp.context.result = {"condition": "Per User max container limit exceeded"}
            resp.status = falcon.HTTP_412
            return
        try:
            image = req.context.doc.get('image', self.config['DEFAULTIMG'])
        except AttributeError:
            image = self.config['DEFAULTIMG']
            self.lgr.info("No image specified, default {post_dct['image']} used")

        # Get the remove option, default remove container on stop
        try:
            post_dct['remove'] = req.context.doc['remove']
            self.lgr.debug(f"Remove: {post_dct['remove']}")
            if post_dct['remove'] not in (True, False):
                post_dct['remove'] = True
        except (AttributeError, KeyError):
            self.lgr.info("No remove option specified")
            post_dct['remove'] = True
        self.lgr.debug(f"Final value of Remove: {post_dct['remove']}")

        # Get the command line arguments
        try:
            cmdlst = req.context.doc['command']
        except (AttributeError, KeyError):
            self.lgr.info("No command line args specified")

        # Get the network mode, For CDP ML image network_mode should be host
        if image == self.config['DEFAULTIMG']:
            post_dct['network_mode'] = 'host'
            post_dct['mounts'] = self.dflt_mnts
            for prt in range(self.config['MINPRT'], self.config['MAXPRT']):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as skt:
                    try:
                        skt.settimeout(0.25)
                        skt.connect((self.config['ip'], prt))
                    except ConnectionRefusedError:
                        port = prt
                        break
            if isinstance(cmdlst, list):
                cmdlst = ["start-process.sh", "--port", str(port)] + cmdlst
            else:
                cmdlst = ["start-process.sh", "--port", str(port)]
        else:
            # Get the mounts
            try:
                post_dct['mounts'] = req.context.doc['mounts']
            except (AttributeError, KeyError):
                self.lgr.info("No mounts specified in the request")

            # Get network mode and the port
            try:
                post_dct['network_mode'] = req.context.doc['network_mode']
                if post_dct['network_mode'] not in ('host', 'bridge', 'overlay'):
                    post_dct['network_mode'] = 'bridge'
            except (AttributeError, KeyError):
                post_dct['network_mode'] = 'bridge' # default bridge network mode
            # Get the ports only when it's not host network_mode
            if post_dct['network_mode'] != 'host':
                try:
                    post_dct['ports'] = req.context.doc['ports']
                except (AttributeError, KeyError):
                    self.lgr.info("No port specified in the request")

        try:
            cpus = req.context.doc['cpus']
            if isinstance(cpus, (float, int)):
                if cpus > self.config['MAXCPU']: # CPU max hard limit
                    post_dct['nano_cpus'] = 1000000000 * self.config['MAXCPU']
                else:
                    post_dct['nano_cpus'] = cpus*1000000000
        except (AttributeError, ValueError, KeyError):
            post_dct['nano_cpus'] = 1000000000 # default 1 CPU

        try:
            post_dct['mem_limit'] = req.context.doc['memory']
            #convert memory request to bytes, verify against max memory limit config
            memdct = {'b':1, 'k':1024, 'm':1048576, 'g':1073741824}
            maxmem = memdct[self.config['MAXMEM'][-1]]*float(self.config['MAXMEM'][:-1])
            if post_dct['mem_limit'][-1] not in memdct:
                post_dct['mem_limit'] = '512m'
            elif memdct[post_dct['mem_limit'][-1]]*float(post_dct['mem_limit'][:-1]) > maxmem:
                post_dct['mem_limit'] = self.config['MAXMEM']
        except (AttributeError, ValueError, KeyError):
            post_dct['mem_limit'] = '512m' # default 512MB


        if len(ulst) == 0:
            post_dct['name'] = self.username
        else:
            cntr = max(each.strip(self.username) for each in ulst)
            if cntr:
                cntr = int(cntr) + 1
            else:
                cntr = 1
            post_dct['name'] = f"{self.username}{cntr}"
        self.lgr.debug(f"Container image: {image}, command: {cmdlst}")
        post_dct['log_config'] = docker.types.LogConfig(config={'mode': 'non-blocking',
                                                                'max-size': '10m',
                                                                'max-file': '3',
                                                                'max-buffer-size': '4m'})
        post_dct['mem_swappiness'] = 0
        post_dct['init'] = True
        post_dct['detach'] = True
        post_dct['tty'] = True
        self.lgr.debug(f"Launching container with the arguments: {post_dct}")
        container = self.dkr.containers.run(image, cmdlst, **post_dct)
        cntrdetails = self.container_info(container.name)
        self.lgr.debug(f"Container launched: {cntrdetails}")
        resp.context.result = cntrdetails
        resp.status = falcon.HTTP_201


app = falcon.App(middleware=[
    RequireJSON(_LOGGER, _CFG),
    JSONTranslator(_LOGGER),
])


dkrsrvr = DkrLaunch(_LOGGER, _CFG)
dkrimages = DkrImages(_LOGGER, _CFG)

app.add_route('/images', dkrimages)
app.add_route('/', dkrsrvr)
app.add_route('/containers', dkrsrvr)

if __name__ == '__main__':
    httpd = simple_server.make_server(socket.gethostbyname(socket.getfqdn()), 8000, app)
    httpd.serve_forever()
