
"""
Core module of the Asynchronous Service Manager

On the diagram below you can see the
work flow of the Asynchronous Service Manager.


                       (6)
         +---------------------------+
         |                           |
  +------+-----+            +--------+-----+           (5)
  |   Client   |            |     PULL     |<-----------------------+                          
  +------------+   (1)      +--------------+                        |
  |    REQ     |----------->|    ROUTER    |----+                   |
  +------------+            +--------------|    |                   |
                            |  Service Mgr |    |                   |
                            +--------------+    | (2)               |
                            |      REP     |    |                   |
                            +--------------+    |                   |
                            |     XPUB     |<---+                   |
                            +------+-------+                        |
                                   |                                |
                                   | (3)                            |
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
                                  |               (4)               | 
                                  +---------------------------------+
  
Workflow explained:

 (1) Client initiates the message flow by
     sending a request to the Service Manager's ROUTER socket.

 (2) The Service Manager distributes the client message to each
     connected node via the XPUB socket.

 (3) Each connected node receives the message via it's SUB socket
     and processes the client request. 

 (4) After processing the client request each node sends back
     results to the Service Manager sink via a PUSH socket.
     Along with the message connection identity is also sent.

 (5) Service Manager's sink receives results from nodes 
     via it's PULL socket. The result message from each node
     also contains connection identity details so that it is
     properly forwarded to clients.

 (6) Client receives results from the Service Manager

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
        self.dist, self.dist_version, self.dist_id = platform.dist()

        linux_service_cmds = {
            'redhat': '/sbin/service',
            'centos': '/sbin/service',
            'debian': '/usr/sbin/service',
        }

        if self.system == 'FreeBSD':
            self.service_cmd = '/usr/sbin/service'
        elif self.system == 'Linux':
            self.service_cmd = linux_service_cmds.get(self.dist, '/usr/sbin/service')

    def run_cmd(self, cmd):
        """
        Execute a service command request

        """
        logging.debug('Executing service request: %s %s %s', self.service_cmd, cmd, self.service_name)

        p = subprocess.Popen([self.service_cmd, self.service_name, cmd],
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
                'stdout':       p.stdout.read(),
                'stderr':       p.stderr.read(),
            }
        }

        return result

