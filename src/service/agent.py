
"""
Service Manager Agent module

"""

import logging
import platform

import zmq

from service.core import Service
from service.core import ServiceManagerException
from service.daemon import Daemon

class ServiceManagerAgent(Daemon):
    """
    Service Manager Agent class

    Extends:
        Daemon class

    Overrides:
        run() method

    """
    def run(self, **kwargs):
        self.time_to_die = False

        self.create_sockets(**kwargs)

        logging.info('Service Manager Agent started')

        while not self.time_to_die:
            socks = dict(self.zpoller.poll())

            # Subscriber socket, receives service request messages
            if socks.get(self.sub_socket):
                logging.debug('Received new message on the subscriber socket')

                topic = self.sub_socket.recv_unicode()
                msg = self.sub_socket.recv_json()

                logging.debug('Topic: %s', topic)
                logging.debug('Message: %s', msg)

                result = self.process_service_req(msg)

                # Add the request id to the result message,
                # so that Service Manager publishes it to the clients
                result['uuid'] = msg['uuid']

                self.sink_socket.send_json(result)
            
            # Management socket
            if socks.get(self.mgmt_socket):
                logging.debug('Received new message on the management socket')
                
                msg = self.mgmt_socket.recv_json()
                
                logging.debug('Message: %s' % msg)

                result = self.process_mgmt_req(msg)
                
                self.mgmt_socket.send_json(result)

        # Shutdown time has arrived, let's cleanup a bit here
        self.close_sockets()
        self.stop()
        
    def create_sockets(self, **kwargs):
        """
        Creates the Service Manager Agent sockets

        """
        logging.debug('Creating Service Manager Agent sockets')

        required_args = (
            'manager_endpoint',
            'sink_endpoint',
            'mgmt_endpoint',
        )

        if not all(k in kwargs for k in required_args):
            raise ServiceManagerException, 'Missing socket endpoints, e.g. manager/sink/mgmt'

        for k in kwargs:
            setattr(self, k, kwargs[k])

        self.zcontext = zmq.Context().instance()

        # Service Manager Agent sockets
        self.sub_socket = self.zcontext.socket(zmq.SUB)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, "")
        
        self.sink_socket = self.zcontext.socket(zmq.PUSH)
        self.mgmt_socket = self.zcontext.socket(zmq.REP)

        self.sub_socket.connect(self.manager_endpoint)
        self.sink_socket.connect(self.sink_endpoint)

        # Bind management socket
        try:
            self.mgmt_socket.bind(self.mgmt_endpoint)
        except zmq.ZMQError as e:
            raise ServiceManagerException, 'Cannot bind management socket: %s' % e

        # Create a poll set for our sockets
        self.zpoller = zmq.Poller()
        self.zpoller.register(self.sub_socket, zmq.POLLIN)
        self.zpoller.register(self.mgmt_socket, zmq.POLLIN)

    def close_sockets(self):
        """
        Closes the Service Manager Agent sockets

        """
        logging.debug('Closing Service Manager Agent sockets')

        self.zpoller.unregister(self.sub_socket)
        self.zpoller.unregister(self.mgmt_socket)

        self.sub_socket.close()
        self.sink_socket.close()
        self.mgmt_socket.close()

        self.zcontext.destroy()

    def process_service_req(self, msg):
        """
        Processes a service request 

        """
        logging.debug('Processing service request')

        # Check for required message fields
        required_attribs = ('cmd', 'service')
        if not all(k in msg for k in required_attribs):
            return { 'success': -1, 'msg': 'Missing message properties' }

        s = Service(msg['service'])

        result = s.run_cmd(msg['cmd'])

        return result

    def process_mgmt_req(self, msg):
        """
        Processes a management request

        """
        logging.debug('Processing management request')

        # Check for required message fields
        required_attribs = (
            'cmd',
        )
        
        if not all(k in msg for k in required_attribs):
            return { 'success': -1, 'msg': 'Missing message properties' }

        mgmt_cmds = {
            'agent.status':   self.agent_status,
            'agent.shutdown': self.agent_shutdown,
        }

        result = mgmt_cmds[msg['cmd']]() if mgmt_cmds.get(msg['cmd']) else { 'success': -1, 'msg': 'Uknown management command requested' }

        return result

    def agent_status(self):
        pass

    def agent_shutdown(self):
        pass
