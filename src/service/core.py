
"""
Core module of the Asynchronous Service Manager

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

