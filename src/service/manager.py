
"""
Service Manager Daemon

"""

import logging

import zmq

from service.core import ServiceManagerException
from service.daemon import Daemon

class ServiceManager(Daemon):
    """
    Service Manager class

    Extends:
        Daemon class

    Overrides:
        run() method

    """
    def run(self, **kwargs):
        """
        Main daemon method 

        """
        self.time_to_die = False

        self.create_listeners(**kwargs)

        logging.info('Service Manager started')

        while not self.time_to_die:
            socks = dict(self.zpoller.poll())

            # Frontend socket, dispatch message to the subscribers
            if socks.get(self.frontend_socket):
                # The routing envolope looks like this:
                #
                # Frame 1:  [ N ][...]  <- Identity of connection
                # Frame 2:  [ 0 ][]     <- Empty delimiter frame
                # Frame 3:  [ N ][...]  <- Data frame
                _id    = self.frontend_socket.recv()
                _empty = self.frontend_socket.recv()
                msg    = self.frontend_socket.recv_json()
                print 'received message on the frontend socket'

            # Backend socket, agents subscribing
            if socks.get(self.backend_socket):
                print 'received message on the backend socket'

            # Sink socket
            if socks.get(self.sink_socket):
                print 'received message on the sink socket'

            # Management socket
            if socks.get(self.mgmt_socket):
                print 'received message on the management socket'

        # Shutdown time has arrived, let's cleanup a bit here
        self.close_listeners()
        self.stop()

    def create_listeners(self, **kwargs):
        """
        Creates the ServiceManager listeners

        """
        required_args = ('frontend_endpoint',
                         'backend_endpoint',
                         'mgmt_endpoint',
                         'sink_endpoint')

        if not all(k in kwargs for k in required_args):
            raise ServiceManagerException, 'Missing socket endpoints, e.g. frontend/backend/mgmt/sink'

        for k in kwargs:
            setattr(self, k, kwargs[k])

        self.zcontext = zmq.Context().instance()

        # ServiceManager sockets
        self.frontend_socket = self.zcontext.socket(zmq.ROUTER)
        self.backend_socket = self.zcontext.socket(zmq.XPUB)
        self.sink_socket = self.zcontext.socket(zmq.PULL)
        self.mgmt_socket = self.zcontext.socket(zmq.REP)
        
        try:
            self.frontend_socket.bind(self.frontend_endpoint)
            self.backend_socket.bind(self.backend_endpoint)
            self.sink_socket.bind(self.sink_endpoint)
            self.mgmt_socket.bind(self.mgmt_endpoint)
        except zmq.ZMQError as e:
            raise ServiceManagerException, 'Cannot bind Service Manager sockets: %s' % e

        # Create a poll set for our sockets
        self.zpoller = zmq.Poller()
        self.zpoller.register(self.frontend_socket, zmq.POLLIN)
        self.zpoller.register(self.backend_socket, zmq.POLLIN)
        self.zpoller.register(self.sink_socket, zmq.POLLIN)
        self.zpoller.register(self.mgmt_socket, zmq.POLLIN)

    def close_listeners(self):
        """
        Closes the Service Manager sockets

        """
        self.zpoller.unregister(self.frontend_socket)
        self.zpoller.unregister(self.backend_socket)
        self.zpoller.unregister(self.sink_socket)
        self.zpoller.unregister(self.mgmt_socket)

        self.frontend_socket.close()
        self.backend_socket.close()
        self.sink_socket.close()
        self.mgmt_socket.close()

        self.zcontext.destroy()
