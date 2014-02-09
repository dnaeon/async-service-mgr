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
        """
        Main daemon method

        """
        # A flag to indicate whether our daemon should be stopped
        self.time_to_die = False

        # Create the Service Manager Agent sockets
        self.create_sockets(**kwargs)

        logging.info('Service Manager Agent started')

        # Main daemon loop
        while not self.time_to_die:
            socks = dict(self.zpoller.poll())

            # Subscriber socket, receives service request messages
            if socks.get(self.sub_socket):
                self.process_sub_msg()

            # Management socket, receives management messages
            if socks.get(self.mgmt_socket):
                self.process_mgmt_msg()

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

        # Service Manager Subscriber socket
        # Subscribe to every topic defined in the conf file.
        # Also subscribe to topics related to the platform on
        # which our Agent runs, e.g. FreeBSD, Linux, etc.
        self.zcontext = zmq.Context().instance()
        self.sub_socket = self.zcontext.socket(zmq.SUB)

        if hasattr(self, 'topics'):
            for eachTopic in self.topics:
                self.sub_socket.setsockopt(zmq.SUBSCRIBE, eachTopic)

        self.sub_socket.setsockopt(zmq.SUBSCRIBE, platform.system())
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, platform.node())
        
        self.sink_socket = self.zcontext.socket(zmq.PUSH)
        self.mgmt_socket = self.zcontext.socket(zmq.REP)

        self.sub_socket.connect(self.manager_endpoint)
        self.sink_socket.connect(self.sink_endpoint)

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

    def process_sub_msg(self):
        """
        Processes a message on the subscriber socket

        The message we receive on the subscriber socket:

            Frame 1: [ N ][...] <- Topic of the message
            Frame 2: [ N ][...] <- Data frame

        The message we receive also contains the unique request id,
        which is later included in the result message before pushing
        results back to the Service Manager sink.

        The unique service request id is included in the result message,
        so that Service Manager publishes the results with the request id
        to the Result Publisher socket.

        The message we receive on the subscriber socket should be in
        JSON format. An example message received on the socket could
        look like this:

            {
                "cmd":     "status",
                "service": "sshd",
                "topic":   "FreeBSD",
                "uuid":    "<unique-client-request-id>",
            }

        """
        logging.debug('Received new message on the subscriber socket')

        topic = self.sub_socket.recv_unicode()
        msg = self.sub_socket.recv_json()

        logging.debug('Topic: %s', topic)
        logging.debug('Message: %s', msg)

        result = self.process_service_req(msg)
                
        # Add the unique request id to the result message,
        # so that Service Manager publishes it to the clients
        result['uuid'] = msg['uuid']

        self.sink_socket.send_json(result)

    def process_mgmt_msg(self):
        """
        Processes a message on the management socket

        This method is used for processing tasks which are
        management related, e.g. getting status information
        from the Service Manager Agent or shutting down the Agent.

        The message should be in JSON format and an example
        management message could look like this:

            {
                "cmd": "agent.status",
            }

        """
        logging.debug('Received new message on the management socket')
                
        msg = self.mgmt_socket.recv_json()
        
        logging.debug('Message: %s' % msg)

        if not isinstance(msg, dict):
            self.mgmt_socket.send_json({ 'success': -1, 'msg': 'Request message should be in JSON format' })

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

        result = mgmt_cmds[msg['cmd']](msg) if mgmt_cmds.get(msg['cmd']) else { 'success': -1, 'msg': 'Uknown management command requested' }

        self.mgmt_socket.send_json(result)

    def process_service_req(self, msg):
        """
        Processes a service request

        Executes the user service(8) request returns the results.

        Args:
            msg (dict): The message containing the service request details

        Returns:
            The result from executing the service request operation

        """
        logging.debug('Processing service request')

        # Check for required message fields
        required_attribs = (
            'cmd',
            'service'
        )
        
        if not all(k in msg for k in required_attribs):
            return { 'success': -1, 'msg': 'Missing message properties' }

        s = Service(msg['service'])

        result = s.run_cmd(msg['cmd'])

        return result

    def agent_status(self, msg):
        """
        Get status information about the Service Manager Agent

        Args:
            msg (dict): The original message as received on mgmt socket (ignored)

        """
        result = {
            'success': 0,
            'msg': 'Service Manager Agent Status',
            'result': {
                'status': 'running',
                'uname': platform.uname(),
                'manager_endpoint': self.manager_endpoint,
                'sink_endpoint': self.sink_endpoint,
                'mgmt_endpoint': self.mgmt_endpoint,
            }
        }

        return result

    def agent_shutdown(self, msg):
        """
        Initiates the Service Manager Agent shutdown sequence

        Args:
            msg (dict): The original message as received on the mgmt socket (ignored)

        """
        logging.info('Service Manager Agent is shutting down')

        self.time_to_die = True

        return { 'success': 0, 'msg': 'Service Manager Agent is shutting down' }
