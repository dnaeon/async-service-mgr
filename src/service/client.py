
"""
Service Manager Client module

"""   

import logging

import zmq

class ServiceManagerClient(object):
    """
    Service Manager Client class

    Defines methods for use by clients for sending out message requests.

    Returns:
        The result message back to the client
        
    """
    def __init__(self, endpoint):
        """
        Initializes a ServiceManagerClient object

        Args:
            endpoint (str): Endpoint we connect the client to

        """
        self.endpoint = endpoint

    def simple_request(self, msg, retries=3, timeout=3000):
        """
        Service Manager Client method for sending out simple requests

        The simple request method is useful for sending out requests
        with a retry mechanism and wait for a single answer on the receiving socket.

        Example use cases are for sending out management messages to daemons.

        Partially based on the Lazy Pirate Pattern:

            - http://zguide.zeromq.org/py:all#Client-Side-Reliability-Lazy-Pirate-Pattern

        Args:
            msg     (dict): The client message to send
            retries  (int): Number of retries
            timeout  (int): Timeout after that number of milliseconds
            
        """
        self.retries = retries
        self.timeout = timeout

        self.zcontext = zmq.Context().instance()
        
        self.zclient = self.zcontext.socket(zmq.REQ)
        self.zclient.connect(self.endpoint)
        self.zclient.setsockopt(zmq.LINGER, 0)

        self.zpoller = zmq.Poller()
        self.zpoller.register(self.zclient, zmq.POLLIN)
        
        result = None
        
        while self.retries > 0:
            # Send our message out
            self.zclient.send_json(msg)
            
            socks = dict(self.zpoller.poll(self.timeout))

            # Do we have a reply?
            if socks.get(self.zclient) == zmq.POLLIN:
                result = self.zclient.recv()
                break
            else:
                # We didn't get a reply back from the server, let's retry
                self.retries -= 1
                logging.warning("Did not receive a reply, retrying...")
                
                # Socket is confused. Close and remove it.
                self.zclient.close()
                self.zpoller.unregister(self.zclient)

                # Re-establish the connection
                self.zclient = self.zcontext.socket(zmq.REQ)
                self.zclient.connect(self.endpoint)
                self.zclient.setsockopt(zmq.LINGER, 0)
                self.zpoller.register(self.zclient, zmq.POLLIN)

        # Close the socket and terminate the context
        self.zclient.close()
        self.zpoller.unregister(self.zclient)
        self.zcontext.term()

        # Did we have any result reply at all?
        if not result:
            logging.error("Did not receive a reply, aborting...")
            return { "success": -1, "msg": "Did not receive a reply, aborting..." }
        
        return result
