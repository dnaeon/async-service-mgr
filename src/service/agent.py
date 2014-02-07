
"""
Service Manager Agent module

"""

import logging

import zmq

from service.core import ServiceManagerException
from service.daemon import Daemon

class ServiceManagerAgent(Daemon):
    """
    Service Manager Agent

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

            # Subscriber socket, process new request message
            if socks.get(self.sub_socket):
                logging.debug('Received new message on the subscriber socket')
                msg = self.sub_socket.recv_json()
                logging.debug('Message: %s' % msg)
                
                self.sink_socket.send_json(msg)
            
            # Management socket
            if socks.get(self.mgmt_socket):
                logging.debug('Received new message on the management socket')
                msg = self.mgmt_socket.recv_json()
                logging.debug('Message: %s' % msg)

        # Shutdown time has arrived, let's cleanup a bit here
        self.close_sockets()
        self.stop()
        
    def create_sockets(self, **kwargs):
        """
        Creates the Service Manager Agent sockets

        """
        required_args = (
            'manager_endpoint',
            'sink_endpoint',
            'mgmt_endpoint',
        )

        if not all(k in kwargs for k in required_args):
            raise ServiceManagerException, 'Missing socket endpoints, e.g. manager/sink/mgmt'

        logging.debug('Creating Service Manager Agent sockets')

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
        
