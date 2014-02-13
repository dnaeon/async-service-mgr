# Copyright (c) 2014 Marin Atanasov Nikolov <dnaeon@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer
#    in this position and unchanged.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR(S) ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR(S) BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Core module of the Asynchronous Service Manager

On the diagram below you can see the
workflow of the Asynchronous Service Manager.
     

                     (3)
        +--------------------------+
        |            (9)           |
        |                   +--------------+
        |              +--->|     PUB      |
  +-----+------+   (8) |    +--------------+           (7)
  |    SUB     |       +----|     PULL     |<-----------------------+                          
  +------------+            +--------------+                        |
  |   Client   |      +---->|    ROUTER    |----+                   |
  +------------+  (1) |     +--------------|    |                   |
  |    REQ     |<-----+     |  Service Mgr |    |                   |
  +------------+  (2)       +--------------+    | (4)               |
                            |      REP     |    |                   |
                            +--------------+    |                   |
                            |     XPUB     |<---+                   |
                            +------+-------+                        |
                                   |                                |
                                   | (5)                            |
                                   |                                |
           +-----------------------+--------------------+           |
           |                       |                    |           |
     +-----+-----+          +------------+        +-----------+     |
     |    SUB    |          |    SUB     |        |    SUB    |     |
     +-----------+          +------------+        +-----------+     |
     |   Node 1  |          |   Node 2   |        |   Node 3  |     |
     +-----------+          +------------+        +-----------+     |
     |    PUSH   |          |    PUSH    |        |    PUSH   |     |
     +-----+-----+          +-----+------+        +-----+-----+     |
           |                      |                     |           |
           +----------------------+---------------------+           |
                                  |                                 |
                                  |               (6)               | 
                                  +---------------------------------+
  
Workflow explained:

 (1) Client initiates the message flow by
     sending a request for service id to the Service Manager

 (2) Service Manager receives client request and returns a
     unique service request id to the client and port number of
     the Result Publisher socket

 (3) Client subscribes to the Service Manager Result Publisher
     and listens for topics with the acquired service request id

 (4) The Service Manager distributes the client service request
     to each connected node via the XPUB socket and passes the
     service request id along with the message

 (5) Each connected node receives the message via it's SUB socket
     and processes the client request

 (6) After processing the client request each node sends back
     results to the Service Manager sink via a PUSH socket along
     with the service request id in the message

 (7) Service Manager's sink receives results from nodes 
     via it's PULL socket. The result message from each node
     is received along with details about the service request id

 (8) The result message is published on the Service Manager's
     Result Publisher socket with topic set to the unique
     service request id

 (9) Subscribed clients receive the result message 

"""

import logging
import platform
import subprocess

class ServiceManagerException(Exception):
    """
    Generic Service Manager Exception

    """
    pass

class Service(object):
    """
    Service class

    Defines methods for managing services via service(8)

    """
    def __init__(self, name):
        """
        Initializes a new Service object
        
        Args:
            name (str): The name of the service 

        """
        self.service_name = name
        self.system = platform.system()
        self.node = platform.node()
        self.version = platform.version()

        # Try to determine the path to the local service(8) manager
        p = subprocess.Popen(
            ['which', 'service'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.service_cmd = p.stdout.read().strip()

    def run_cmd(self, cmd):
        """
        Execute a service command request

        Args:
            cmd (str): The command to pass to service(8)

        Returns:
            The result of the service(8) operation

        """
        logging.debug(
            'Executing service request: %s %s %s',
            self.service_cmd,
            self.service_name,
            cmd
        )

        if not self.service_cmd:
            return {
                'success': -1,
                'msg': 'Unable to determine location to service(8)',
                'node': self.node
            }

        p = subprocess.Popen(
            [self.service_cmd, self.service_name, cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        p.wait()
        
        result = {
            'msg': 'Executed service %s request' % cmd,
            'result': {
                'node':         self.node,
                'service':      self.service_name,
                'returncode':   p.returncode,
                'stdout':       p.stdout.read().split('\n'),
                'stderr':       p.stderr.read().split('\n'),
                'system':       self.system,
                'version':      self.version,
            }
        }

        return result

