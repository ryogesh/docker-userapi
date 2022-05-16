# docker-userapi
Lightweight api to manage limited docker actions without root user access.


## Overview
Root user manages docker container for users. e.g. start, stop, run. 
This API exposes limited actions to the end users without the need for root user.
End user(s) can invoke the API to perform start, stop, restart, run, delete.

There are 2 endpoints on the api 
- /images
	- get :- Get list of all available docker images on the node
- / or /containers
	- get :- list of containers belonging to the user
	- put :- start, stop, restart a container
	- post :- create/run a container
 	- delete :- remove(force) the container 

Default config values are set in config.yml file and is expected to be in the same folder as dkrserver.py. 

Examples shown below uses httpie. 

## Required python packages
- falcon 
- pyyaml
- docker

## Running the falcon WSGI server

API can be run using any WSGI server, e.g. uWSGI or Gunicorn. Or can be run directly on port 8000 as shown below 
```
# python dkrserver.py
192.168.56.10 - - [14/May/2022 22:22:39] "OPTIONS /images HTTP/1.1" 200 0
192.168.56.10 - - [14/May/2022 22:05:27] "OPTIONS / HTTP/1.1" 200 0
```

## Security
There is no authentication or authorization on the api. API can be configured to force an username in the header using the config value
HEADERTOKEN : True


In such a case, if the username header is missing, API returns an error
```
# http OPTIONS http://192.168.56.10:8000
HTTP/1.0 401 Unauthorized
Date: Sun, 15 May 2022 02:04:54 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 94
content-type: application/json
vary: Accept

{
    "description": "username required in request header",
    "title": "username required in header"
}

```

## Invoking the API with a particular loglevel
API logfile name is dkrApiEngine.log. Default loglevel is WARNING.

API call can set a loglevel. Once loglevel is set on a request, loglevel remains active on all future requests.To reset/change, set to another value in a future request.
Supported loglevels are 10, 20, 30, 40 and 50 or "INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL" respectively.


## Supported methods on the endpoints with different loglevel settings

```
# echo '{"loglevel":"DEBUG"}' | http OPTIONS http://192.168.56.10:8000/images username:ryogesh
HTTP/1.0 200 OK
Date: Sun, 15 May 2022 02:22:39 GMT
Server: WSGIServer/0.2 CPython/3.9.7
allow: GET
content-length: 0
content-type: application/json


(base) [root@cbase docfile]# echo '{"loglevel":"WARNING"}' | http OPTIONS http://192.168.56.10:8000/ username:ryogesh
HTTP/1.0 200 OK
Date: Sun, 15 May 2022 02:23:02 GMT
Server: WSGIServer/0.2 CPython/3.9.7
allow: DELETE, GET, POST, PUT
content-length: 0
content-type: application/json

```

## Get list of available images

```
# http GET http://192.168.56.10:8000/images
HTTP/1.0 200 OK
Date: Sat, 14 May 2022 23:56:00 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 616
content-type: application/json

{
    "Available Images": [
        {
            "created": "2022-05-03T15:12:45.760329847Z",
            "short id": "sha256:adf9889d91",
            "size": "3,622.46MB",
            "tags": [
                "cdp_ml:v1"
            ]
        },
        {
            "created": "2022-04-20T10:43:12.055940177Z",
            "short id": "sha256:fa5269854a",
            "size": "134.97MB",
            "tags": [
                "nginx:latest"
            ]
        },
        {
            "created": "2022-02-02T18:33:25.499017947Z",
            "short id": "sha256:018184f167",
            "size": "1,190.37MB",
            "tags": [
                "docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-jupyterlab-python3.9-standard:2021.12.1-b17"
            ]
        },
        {
            "created": "2021-09-15T18:20:23.99863383Z",
            "short id": "sha256:eeb6ee3f44",
            "size": "194.49MB",
            "tags": [
                "centos:7.9.2009"
            ]
        }
    ]
}
```

## GET list of containers for an user
If a running container exposes a port then that information is available in "application url". 

```
# http GET http://192.168.56.10:8000/containers username:ryogesh
HTTP/1.0 200 OK
Date: Sun, 15 May 2022 00:16:28 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 1277
content-type: application/json

{
    "Running Containers": [
        {
            "application url": "cbase.my.site:3333",
            "container details": {
                "Cpus": 1.0,
                "Created": "2022-05-15T00:10:32.336874975Z",
                "Image": "nginx:latest",
                "Memory": "512MB",
                "Mounts": [],
                "StartedAt": "2022-05-15T00:10:33.155171514Z",
                "Status": "running"
            },
            "container id": "490f29d2ea",
            "container name": "ryogesh1"
        },
        {
            "application url": "cbase.my.site:8888",
            "container details": {
                "Cpus": 1.0,
                "Created": "2022-05-15T00:05:13.925793517Z",
                "Image": "cdp_ml:v1",
                "Memory": "512MB",
                "Mounts": [
                    {
                        "Destination": "/usr/share/javazi-1.8",
                        "Mode": "",
                        "Propagation": "rprivate",
                        "RW": false,
                        "Source": "/usr/share/javazi-1.8",
                        "Type": "bind"
                    },
                    {
                        "Destination": "/etc/krb5.conf",
                        "Mode": "",
                        "Propagation": "rprivate",
                        "RW": false,
                        "Source": "/etc/krb5.conf",
                        "Type": "bind"
                    },
                    {
                        "Destination": "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.322.b06-1.el7_9.x86_64/jre",
                        "Mode": "",
                        "Propagation": "rprivate",
                        "RW": false,
                        "Source": "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.322.b06-1.el7_9.x86_64/jre",
                        "Type": "bind"
                    },
                    {
                        "Destination": "/usr/share/java",
                        "Mode": "",
                        "Propagation": "rprivate",
                        "RW": false,
                        "Source": "/usr/share/java",
                        "Type": "bind"
                    }
                ],
                "StartedAt": "2022-05-15T00:05:14.379046393Z",
                "Status": "exited"
            },
            "container id": "f608d30268",
            "container name": "ryogesh"
        }
    ]
}
```

##  Launch a container for an user

Number of containers an user can launch is restricted by the config value
MAX_PER_USER : 3

Container name is always set to username{cntr}. e.g. ryogesh, ryogesh1, ryogesh2 etc.

POST request accepts the following
- image :- default is cdp_ml:v1 image. Refer [CDP ML Docker image](https://github.com/ryogesh/jupyterlab-centos-docker)
- commands :- default None
- remove :- Remove the container on stop. default True
- network_mode :-  'host', 'bridge', 'overlay' . default 'bridge'
- cpus :- e.g. 1.5 default 1
- mem_limit :- e.g. 1073741824b, 1048576k, 1024m or 1g. default 512m
- ports:- default None
- mounts:- default None

Create a container using the default cdp_ml:v1 image with 
- on stop, not to remove the container.
- additional command line options to disable JupyterLab from prompting for user token or password. [Not Recommended](https://jupyter-notebook.readthedocs.io/en/stable/security.html#alternatives-to-token-authentication)
```
# echo '{"remove": false, "command": ["--NotebookApp.token=", "--NotebookApp.password="]}' | http POST http://192.168.56.10:8000  username:ryogesh
HTTP/1.0 201 Created
Date: Sun, 15 May 2022 01:49:12 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 943
content-type: application/json

{
    "application url": "cbase.my.site:8888",
    "container details": {
        "Cpus": 1.0,
        "Created": "2022-05-15T01:49:12.103845287Z",
        "Image": "cdp_ml:v1",
        "Memory": "512MB",
        "Mounts": [
            {
                "Destination": "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.322.b06-1.el7_9.x86_64/jre",
                "Mode": "",
                "Propagation": "rprivate",
                "RW": false,
                "Source": "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.322.b06-1.el7_9.x86_64/jre",
                "Type": "bind"
            },
            {
                "Destination": "/usr/share/java",
                "Mode": "",
                "Propagation": "rprivate",
                "RW": false,
                "Source": "/usr/share/java",
                "Type": "bind"
            },
            {
                "Destination": "/usr/share/javazi-1.8",
                "Mode": "",
                "Propagation": "rprivate",
                "RW": false,
                "Source": "/usr/share/javazi-1.8",
                "Type": "bind"
            },
            {
                "Destination": "/etc/krb5.conf",
                "Mode": "",
                "Propagation": "rprivate",
                "RW": false,
                "Source": "/etc/krb5.conf",
                "Type": "bind"
            }
        ],
        "StartedAt": "2022-05-15T01:49:12.600218857Z",
        "Status": "running"
    },
    "container id": "4c01c747a8",
    "container name": "ryogesh1"
}
```
Another example
Create a nginx container
- on stop, not to remove the container.
- expose the container port 80 to host port 3333
- Set loglevel to debug when invoking the API

```
# echo '{"loglevel":"debug", "remove": false, "ports": {"80/tcp": 3333}, "image": "nginx:latest"}' | http -h -b POST http://192.168.56.10:8000  username:ryogesh
{
    "application url": "cbase.my.site:3333",
    "container details": {
        "Cpus": 1.0,
        "Created": "2022-05-15T00:10:32.336874975Z",
        "Image": "nginx:latest",
        "Memory": "512MB",
        "Mounts": [],
        "StartedAt": "2022-05-15T00:10:33.155171514Z",
        "Status": "running"
    },
    "container id": "490f29d2ea",
    "container name": "ryogesh1"
}
```

##  Start, Stop or Restart a container

Accepts the following 
- action: stop, start, restart
- "container name" or "container id"

In case an incorrect container name or id is provided or if the container doesn't belong to the user then an error is shown
```
# echo '{"loglevel":10, "container name":"system1", "action": "stop" }' | http PUT http://192.168.56.10:8000
HTTP/1.0 412 Precondition Failed
Date: Sat, 14 May 2022 23:56:42 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 104
content-type: application/json

{
    "Action stop failed": "Invalid action or invalid container or container doesn't belong to user system"
}
```

stop the container with name ryogesh.
```
# echo '{"container name":"ryogesh", "action": "stop" }' |http PUT http://192.168.56.10:8000  username:ryogesh
HTTP/1.0 200 OK
Date: Sun, 15 May 2022 00:05:59 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 969
content-type: application/json

{
    "Action stop successful": {
        "application url": "cbase.my.site:8888",
        "container details": {
            "Cpus": 1.0,
            "Created": "2022-05-15T00:05:13.925793517Z",
            "Image": "cdp_ml:v1",
            "Memory": "512MB",
            "Mounts": [
                {
                    "Destination": "/usr/share/java",
                    "Mode": "",
                    "Propagation": "rprivate",
                    "RW": false,
                    "Source": "/usr/share/java",
                    "Type": "bind"
                },
                {
                    "Destination": "/usr/share/javazi-1.8",
                    "Mode": "",
                    "Propagation": "rprivate",
                    "RW": false,
                    "Source": "/usr/share/javazi-1.8",
                    "Type": "bind"
                },
                {
                    "Destination": "/etc/krb5.conf",
                    "Mode": "",
                    "Propagation": "rprivate",
                    "RW": false,
                    "Source": "/etc/krb5.conf",
                    "Type": "bind"
                },
                {
                    "Destination": "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.322.b06-1.el7_9.x86_64/jre",
                    "Mode": "",
                    "Propagation": "rprivate",
                    "RW": false,
                    "Source": "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.322.b06-1.el7_9.x86_64/jre",
                    "Type": "bind"
                }
            ],
            "StartedAt": "2022-05-15T00:05:14.379046393Z",
            "Status": "exited"
        },
        "container id": "f608d30268",
        "container name": "ryogesh"
    }
}
```


##  Delete a container
Container is force deleted.
```
# echo '{"container name":"ryogesh" }' |http DELETE http://192.168.56.10:8000  username:ryogesh
HTTP/1.0 200 OK
Date: Sun, 15 May 2022 00:03:20 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 62
content-type: application/json

{
    "Delete successful": "Container name:ryogesh, id:ad84c52aa3"
}
```
In case an incorrect container name or id is provided or if the container doesn't belong to the user then an error is shown
```
# echo '{"loglevel":"warning", "container name":"system" }' |http DELETE http://192.168.56.10:8000  username:ryogesh
HTTP/1.0 412 Precondition Failed
Date: Sun, 15 May 2022 00:03:00 GMT
Server: WSGIServer/0.2 CPython/3.9.7
content-length: 72
content-type: application/json

{
    "Delete failed": "Invalid container or doesn't belong to user ryogesh"
}
```
