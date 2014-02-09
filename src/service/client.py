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
Service Manager Client module

Defines classes for sending out client requests to a
Service Manager.

"""   

import logging

from time import time

import zmq

class ServiceManagerClient(object):
    """
    Service Manager Client class

    Defines methods for use by clients for sending out message requests.

    Returns:
        The result message back to the client
        
    """
    def __init__(self):
        """
        Initializes a ServiceManagerClient object

        """
        pass

    def simple_request(self, msg, endpoint, retries=3, timeout=1000):
        """
        Service Manager Client method for sending out simple requests

        The simple request method is useful for sending out requests
        with a retry mechanism and wait for a single answer on the receiving socket.

        Example use cases are for sending out management messages to daemons, or
        acquiring service request ids.

        Partially based on the Lazy Pirate Pattern:

            - http://zguide.zeromq.org/py:all#Client-Side-Reliability-Lazy-Pirate-Pattern

        Args:
            msg     (dict): The client message to send
            retries  (int): Number of retries
            timeout  (int): Timeout after that number of milliseconds
            
        """
        self.msg      = msg
        self.endpoint = endpoint
        self.retries  = retries
        self.timeout  = timeout

        self.zcontext = zmq.Context().instance()
        
        self.zclient = self.zcontext.socket(zmq.REQ)
        self.zclient.connect(self.endpoint)
        self.zclient.setsockopt(zmq.LINGER, 0)

        self.zpoller = zmq.Poller()
        self.zpoller.register(self.zclient, zmq.POLLIN)
        
        result = None
        
        while self.retries > 0:
            # Send our message out
            self.zclient.send_json(self.msg)
            
            socks = dict(self.zpoller.poll(self.timeout))

            # Do we have a reply?
            if socks.get(self.zclient) == zmq.POLLIN:
                result = self.zclient.recv_json()
                break
            else:
                # We didn't get a reply back from the server, let's retry
                self.retries -= 1
                logging.warning("Did not receive a reply, retrying...")
                
                # Socket is confused. Close and remove it.
                self.zpoller.unregister(self.zclient)
                self.zclient.close()

                # Re-establish the connection
                self.zclient = self.zcontext.socket(zmq.REQ)
                self.zclient.connect(self.endpoint)
                self.zclient.setsockopt(zmq.LINGER, 0)
                self.zpoller.register(self.zclient, zmq.POLLIN)

        # Close the socket and terminate the context
        self.zpoller.unregister(self.zclient)
        self.zclient.close()
        self.zcontext.term()

        # Did we have any result reply at all?
        if not result:
            logging.error("Did not receive a reply, aborting...")
            return { "success": -1, "msg": "Did not receive a reply, aborting..." }
        
        return result

    def wait_for_publisher_msgs(self, endpoint, topic, wait_time):
        """
        Subscribes to an endpoint for messages with specific topic

        Once we acquire a service request id from Service Manager we
        would want to get our results back. This method subscribes to the
        Service Manager Result Publisher endpoint and waits for any messages
        with the unique service request id as the topic.

        Args:
            endpoint    (str): Endpoint we subscribe to
            topic       (str): The topic we subscribe to
            wait_time (float): Wait maximum that amount of seconds

        Returns:
            A list of messages received by the publisher

        """
        self.endpoint  = endpoint
        self.topic     = topic
        self.wait_time = wait_time

        logging.debug('Endpoint: %s', self.endpoint)
        logging.debug('Topic: %s', self.topic)
        logging.debug('Wait time: %f seconds', self.wait_time)

        self.zcontext = zmq.Context().instance()
        self.zclient  = self.zcontext.socket(zmq.SUB)
        self.zclient.connect(self.endpoint)
        self.zclient.setsockopt(zmq.SUBSCRIBE, str(self.topic))

        self.zpoller = zmq.Poller()
        self.zpoller.register(self.zclient, zmq.POLLIN)

        self.wait_start = time()

        result = []

        while (time() - self.wait_start) <= self.wait_time:
            socks = dict(self.zpoller.poll(50))

            if socks.get(self.zclient):
                _topic = self.zclient.recv()
                result.append(self.zclient.recv_json())

        self.zpoller.unregister(self.zclient)
        self.zclient.close()
        self.zcontext.term()
            
        return result
    
                
