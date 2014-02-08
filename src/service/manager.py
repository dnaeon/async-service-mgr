
"""
Service Manager Daemon

"""

import uuid
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

            # Frontend socket, clients are requesting a service id
            if socks.get(self.frontend_socket):
                logging.debug('Received message on the frontend socket')
                
                # The routing envelope looks like this:
                #
                # Frame 1:  [ N ][...]  <- Identity of connection
                # Frame 2:  [ 0 ][]     <- Empty delimiter frame
                # Frame 3:  [ N ][...]  <- Data frame
                _id    = self.frontend_socket.recv()
                _empty = self.frontend_socket.recv()
                msg    = self.frontend_socket.recv_json()

                logging.debug('ID: %s', _id)
                logging.debug('Message: %s', msg)
                logging.debug('Generating client id for result collecting')

                # Generate a service request id for our client and ask them to
                # subscribe to the result publisher endpoint in order to receive
                # their results
                req_id = uuid.uuid4().get_hex()
                self.frontend_socket.send(_id, zmq.SNDMORE)
                self.frontend_socket.send("", zmq.SNDMORE)
                self.frontend_socket.send_json({'uuid': req_id, 'port': self.result_pub_port})

                logging.debug('Client service request id is: %s', req_id)

                # The message we send to the backend also contains the client
                # service request id as well. This is done so later when we receive
                # the results in the sink we can route the results to the clients properly
                msg['uuid'] = req_id

                logging.debug('Sending message to backend for processing')
                
                self.backend_socket.send_unicode(msg['topic'], zmq.SNDMORE)
                self.backend_socket.send_json(msg)

            # Backend socket, agents are (un)subscribing to/from it
            if socks.get(self.backend_socket):
                logging.debug('Received message on the backend socket')

                msg = self.backend_socket.recv()
                topic = 'any' if not msg[1:] else msg[1:]
                if msg[0] == '\x01':
                    logging.debug('Agent subscribed to topic: %s', topic)
                elif msg[0] == '\x00':
                    logging.debug('Agent unsubscribed from topic: %s', topic)

            # Sink socket, collects results from the backend agents
            if socks.get(self.sink_socket):
                logging.debug('Received message on the sink socket')
                
                msg = self.sink_socket.recv_json()

                logging.debug('Message: %s', msg)

                # Publish the results to the clients using the
                # request id of the service request as the topic
                self.result_pub_socket.send_unicode(msg['uuid'], zmq.SNDMORE)
                self.result_pub_socket.send_json(msg)

            # Management socket, receives management commands
            if socks.get(self.mgmt_socket):
                logging.debug('Received message on the management socket')
                
                msg = self.mgmt_socket.recv_json()
                
                logging.debug('Message: %s' % msg)

        # Shutdown time has arrived, let's cleanup a bit here
        logging.info('Service Manager is shutting down')
        
        self.close_listeners()
        self.stop()

    def create_listeners(self, **kwargs):
        """
        Creates the ServiceManager listeners

        """
        # Check for required endpoints args
        required_args = (
            'frontend_endpoint',
            'backend_endpoint',
            'mgmt_endpoint',
            'sink_endpoint'
        )

        if not all(k in kwargs for k in required_args):
            raise ServiceManagerException, 'Missing socket endpoints, e.g. frontend/backend/mgmt/sink'

        for k in kwargs:
            setattr(self, k, kwargs[k])

        logging.debug('Creating Service Manager listeners')

        self.zcontext = zmq.Context().instance()

        # Our Service Manager sockets
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
        loggin.debug('Closing Service Manager listeners')

        self.zpoller.unregister(self.frontend_socket)
        self.zpoller.unregister(self.backend_socket)
        self.zpoller.unregister(self.sink_socket)
        self.zpoller.unregister(self.mgmt_socket)

        self.frontend_socket.close()
        self.backend_socket.close()
        self.sink_socket.close()
        self.mgmt_socket.close()

        self.zcontext.destroy()
