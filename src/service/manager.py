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
Service Manager Daemon

"""

import uuid
import logging
import platform

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
        # A flag to indicate that our daemon should terminate
        self.time_to_die = False

        # Create the Service Manager listeners
        self.create_listeners(**kwargs)

        logging.info('Service Manager started')

        # Main daemon loop
        while not self.time_to_die:
            socks = dict(self.zpoller.poll())

            # Frontend socket, clients are requesting a service id
            if socks.get(self.frontend_socket):
                self.process_frontend_msg()

            # Backend socket, agents are (un)subscribing to/from it
            if socks.get(self.backend_socket):
                self.process_backend_msg()

            # Sink socket, collects results from the backend agents
            if socks.get(self.sink_socket):
                self.process_sink_msg()
  
            # Management socket, receives management commands
            if socks.get(self.mgmt_socket):
                self.process_mgmt_msg()

        # Shutdown time has arrived, let's cleanup a bit here
        self.close_listeners()
        self.stop()

    def create_listeners(self, **kwargs):
        """
        Creates the ServiceManager listeners

        """
        logging.debug('Creating Service Manager listeners')

        # Check for required endpoint args
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

        self.zcontext = zmq.Context().instance()

        # Our Service Manager sockets
        self.frontend_socket   = self.zcontext.socket(zmq.ROUTER)
        self.backend_socket    = self.zcontext.socket(zmq.XPUB)
        self.sink_socket       = self.zcontext.socket(zmq.PULL)
        self.mgmt_socket       = self.zcontext.socket(zmq.REP)
        self.result_pub_socket = self.zcontext.socket(zmq.PUB)

        try:
            self.frontend_socket.bind(self.frontend_endpoint)
            self.backend_socket.bind(self.backend_endpoint)
            self.sink_socket.bind(self.sink_endpoint)
            self.mgmt_socket.bind(self.mgmt_endpoint)
            self.result_pub_port = self.result_pub_socket.bind_to_random_port('tcp://*')
        except zmq.ZMQError as e:
            raise ServiceManagerException, 'Cannot bind Service Manager sockets: %s' % e

        # Create a poll set for our sockets
        self.zpoller = zmq.Poller()
        self.zpoller.register(self.frontend_socket, zmq.POLLIN)
        self.zpoller.register(self.backend_socket, zmq.POLLIN)
        self.zpoller.register(self.sink_socket, zmq.POLLIN)
        self.zpoller.register(self.mgmt_socket, zmq.POLLIN)

        logging.debug('Frontend socket bound to %s', self.frontend_endpoint)
        logging.debug('Backend socket bound to %s', self.backend_endpoint)
        logging.debug('Sink socket bound to %s', self.sink_endpoint)
        logging.debug('Management socket bound to %s', self.mgmt_endpoint)
        logging.debug('Result publisher socket bound to %s', 'tcp://*:' + str(self.result_pub_port))

    def close_listeners(self):
        """
        Closes the Service Manager sockets

        """
        logging.debug('Closing Service Manager listeners')

        self.zpoller.unregister(self.frontend_socket)
        self.zpoller.unregister(self.backend_socket)
        self.zpoller.unregister(self.sink_socket)
        self.zpoller.unregister(self.mgmt_socket)

        self.frontend_socket.close()
        self.backend_socket.close()
        self.sink_socket.close()
        self.mgmt_socket.close()
        self.result_pub_socket.close()

        self.zcontext.destroy()

    def process_frontend_msg(self):
        """
        Processes a message on the frontend socket

        The routing envelope of the message looks like this:

            Frame 1:  [ N ][...]  <- Identity of connection
            Frame 2:  [ 0 ][]     <- Empty delimiter frame
            Frame 3:  [ N ][...]  <- Data frame

        The frontend socket of the Service Manager receives new
        service request commands from clients and prepares a 
        unique service request id for the clients.

        It is up to the client to subscribe to the Service Manager
        Result Publisher endpoint for receiving any results.

        Example client message on the frontend socket could look like this:
        
            {
                "cmd":     "status",
                "service": "sshd",
                "topic":   "FreeBSD",
            }

        The Service Manager's frontend socket replies to the client with a
        unique service request id, so that clients can subscribe for results.
        
            {
                "uuid": "<unique-service-request-id>",
                "port": "<result-publisher-port>",
            }

        """
        logging.debug('Received message on the frontend socket')

        _id    = self.frontend_socket.recv()
        _empty = self.frontend_socket.recv()
        msg    = self.frontend_socket.recv_json()

        logging.debug('ID: %s', _id)
        logging.debug('Message: %s', msg)

        if not isinstance(msg, dict):
            self.frontend_socket.send(_id, zmq.SNDMORE)
            self.frontend_socket.send("", zmq.SNDMORE)
            self.frontend_socket.send_json({ 'success': -1, 'msg': 'Request message should be in JSON format' })
            return

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

    def process_backend_msg(self):
        """
        Processes a message on the backend socket

        The backend socket receives messages from Agents and contains
        information about whether an Agent subscribes or unsubscribes.

        """
        logging.debug('Received message on the backend socket')

        msg = self.backend_socket.recv()
        topic = 'any' if not msg[1:] else msg[1:]
        
        if msg[0] == '\x01':
            logging.debug('Agent subscribed to topic: %s', topic)
        elif msg[0] == '\x00':
            logging.debug('Agent unsubscribed from topic: %s', topic)

    def process_sink_msg(self):
        """
        Processes a message on the sink socket

        The Service Manager sink socket receives the results
        from a service request operation from the Service Manager Agents.

        The received message also contains the unique service request id,
        which is later used as the topic when results are published on the
        Result Publisher socket.

        """
        logging.debug('Received message on the sink socket')
                
        msg = self.sink_socket.recv_json()
        
        logging.debug('Message: %s', msg)

        # Publish the results to the clients using the
        # request id of the service request as the topic
        self.result_pub_socket.send_unicode(msg['uuid'], zmq.SNDMORE)
        self.result_pub_socket.send_json(msg)

    def process_mgmt_msg(self):
        """
        Processes a message on the management socket

        The management socket of Service Manager is used for
        processing management tasks, e.g. getting status information or
        initiating the shutdown sequence of Service Manager.

        The message should be in JSON format.

        Example management message could look like this:
        
            {
                "cmd": "manager.status"
            }

        """
        logging.debug('Received message on the management socket')
                
        msg = self.mgmt_socket.recv_json()

        logging.debug('Message: %s', msg)
        
        if not isinstance(msg, dict):
            self.mgmt_socket.send_json({ 'success': -1, 'msg': 'Request message should be in JSON format' })
            return

        required_attribs = (
            'cmd',
        )
        
        if not all(k in msg for k in required_attribs):
            return { 'success': -1, 'msg': 'Missing message properties' }

        mgmt_cmds = {
            'manager.status':   self.manager_status,
            'manager.shutdown': self.manager_shutdown,
        }

        result = mgmt_cmds[msg['cmd']](msg) if mgmt_cmds.get(msg['cmd']) else { 'success': -1, 'msg': 'Uknown management command requested' }

        self.mgmt_socket.send_json(result)

    def manager_status(self, msg):
        """
        Get status information about the Service Manager

        Args:
            msg (dict): The original management message (ignored)

        """
        result = {
            'success': 0,
            'msg': 'Service Manager Status',
            'result': {
                'status': 'running',
                'uname': platform.uname(),
                'frontend_endpoint': self.frontend_endpoint,
                'backend_endpoint': self.backend_endpoint,
                'sink_endpoint': self.sink_endpoint,
                'mgmt_endpoint': self.mgmt_endpoint,
                'result_publisher_port': self.result_pub_port,
            }
        }

        return result

    def manager_shutdown(self, msg):
        """
        Initiates the Service Manager shutdown sequence

        Args:
            msg (dict): The original management message received (ignored)

        """
        logging.info('Service Manager is shutting down')

        self.time_to_die = True

        return { 'success': 0, 'msg': 'Service Manager is shutting down' }

