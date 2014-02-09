## service-mgr -- Asynchronous service(8) manager for UNIX/Linux

*service-mgr* is an asynchronous `service(8)` manager for UNIX/Linux systems.

*Service Manager* allows you to manage the services of your UNIX/Linux clusters with ease in asynchronous way.

The system consists of a number of components, each responsible for a specific task. The table below summarizes
the `Service Manager` components and their purpose.

| Component          | Purpose                                                            |
|--------------------|--------------------------------------------------------------------|
| service-mgrd       | Service Manager daemon, controls all Service Manager Agents        |
| service-mgr-agentd | Service Manager Agent, responsible for processing service requests |
| service-mgr-client | Client application, used for sending service requests to Agents    |

`Service Manager` uses the great [ZeroMQ](http://zeromq.org/) socket library for bridging components together
and provide us with asynchronous service management.

The typical flow of a service request message can be seen on the diagram below.

![Service Manager Message Flow Diagram](https://raw2.github.com/dnaeon/async-service-mgr/master/src/img/service-mgr-message-flow.jpg)

For more details on the actual message flow, please check the
[Service Manager core module](https://github.com/dnaeon/async-service-mgr/blob/master/src/service/core.py),
which explains the workflow in more details.

## Requirements

* Python 2.7.x
* [pyzmq](https://github.com/zeromq/pyzmq)
* [docopt](https://github.com/docopt/docopt)

## Contributions

`Service Manager` is hosted on Github. Please contribute by reporting issues,
suggesting features or by sending patches using pull requests.

If you like this project please also consider supporting development using [Gittip](https://www.gittip.com/dnaeon/). Thank you!

## Installation

In order to install `Service Manager` simply execute the command below.

	# python setup.py install

And that's it, in the next sections we will see how to configure the `Service Manager` components and see
examples on how to get control over the services of our UNIX/Linux clusters.

## FreeBSD specific notes

In order to run `Service Manager` on your FreeBSD systems, please use the
rc.d scripts from the [FreeBSD rc.d scripts directory](https://github.com/dnaeon/async-service-mgr/tree/master/src/init.d/FreeBSD)

First, copy the scripts to your `/usr/local/etc/rc.d` directory:

	# cp src/init.d/FreeBSD/service-mgr* /usr/local/etc/rc.d

Now enable the services from `/etc/rc.conf`:

	service_mgrd_enable="YES"
	service_mgr_agentd_enable="YES"

## Debian GNU/Linux specific notes

In order to run `Service Manager` on your Debian GNU/Linux systems, please use the
init.d scripts from the [Debian init.d directory](https://github.com/dnaeon/async-service-mgr/tree/master/src/init.d/Debian)

First, copy the scripts to your `/etc/init.d` directory:

	# cp src/init.d/Debian/service-mgr* /etc/init.d/

Now enable the services:

	# update-rc.d service-mgrd defaults
	# update-rc.d service-mgr-agentd defaults

## RHEL/CentOS specific notes

In order to run `Service Manager` on your RHEL/CentOS systems, please use the
init.d scripts from the [CentOS init.d directory](https://github.com/dnaeon/async-service-mgr/tree/master/src/init.d/CentOS)

First, copy the scripts to your `/etc/init.d` directory:

	# cp src/init.d/CentOS/service-mgr* /etc/init.d/

Now enable the services:

	# chkconfig service-mgrd on
	# chkconfig service-mgr-agentd on

## Service Manager Daemon

The `service-mgrd` is the `Service Manager` component which is responsible for processing user service requests
and dispatching of these requests to any connected `Service Manager Agent`.

The `service-mgrd` binds to well-known ports, which the clients and `Agents` connect to.

This component is also the one that takes care of collecting results from our `Agents` and publishing these results
to the clients.

Ideally you would be running the `Service Manager daemon` on at least two nodes bound to a virtual IP address,
so that you can provide redundancy. In case one of the `Service Manager` daemon goes down the second one could
take over and you still retain control over your UNIX/Linux clusters.

The default configuration file of `service-mgrd` resides in `/etc/service-mgr/service-mgrd.conf`, but you can also
specify an alternate config file from the command-line as well.

Below is an example configuration file of `service-mgrd`:

	[Default]
	frontend_endpoint = tcp://*:5500
	backend_endpoint  = tcp://*:5600
	sink_endpoint     = tcp://*:5700
	mgmt_endpoint     = tcp://*:5800

Here is an explanation of the config entries.

| Config option     | Description                                                               |
|-------------------|---------------------------------------------------------------------------|
| frontend_endpoint | This is the endpoint to which clients connect and request a service id    |
| backend_endpoint  | This is the endpoint to which Agents connect and receive service requests |
| sink_endpoint     | This is the endpoint to which Agents send back any results                |
| mgmt_endpoint     | Management endpoint, used for sending management commands                 |

Now, let's start our `service-mgrd` daemon.

	# service service-mgrd start

For more information on the command-line options of `service-mgrd`, please execute the command below:

	# service-mgrd --help
	
Checking the log file at `/var/log/service-mgr/service-mgrd.log` should also indicate that our
Service Manager has started successfully or contain errors if something went wrong.

## Service Manager Agent Daemon

The `service-mgr-agentd` is the `Service Manager Agent` component which is
responsible for processing and executing service requests dispatched from the `Service Manager`.

It is also responsible for sending back any result to the `Service Manager` sink socket, which are
later published to the clients.

The `service-mgr-agentd` connects to the `service-mgrd` daemon and subscribes for messages with
specific *topics*. The topics the `Service Manager Agent` subscribes define whether a message should
be processed by the Agent or ignored.

Example topics that the `Service Manager Agents` subscribes are the Operating System the Agent runs on, e.g.
FreeBSD, Debian GNU/Linux, RHEL, etc.

This allows us to send a service request to systems with a specific characteristics in a cluster, e.g. stop
SSH daemon on all Linux systems, but start it on all FreeBSD systems. We will see later how to send messages
to our `Service Manager Agents` and how to control their services.

The default configuration file of `service-mgr-agentd` resides in `/etc/service-mgr/service-mgr-agentd.conf`,
but you can also specify an alternate config file from the command-line as well.

Below is an example configuration file of `service-mgr-agentd`:

	[Default]
	manager_endpoint  = tcp://localhost:5600
	sink_endpoint     = tcp://localhost:5700
	mgmt_endpoint     = tcp://*:6000

Here is an explanation of the config entries.

| Config option    | Description                                                                |
|------------------|----------------------------------------------------------------------------|
| manager_endpoint | Endpoint of the Service Manager backend socket to which our Agents connect |
| sink_endpoint    | Endpoint of the Service Manager sink socket, used for sending results      |
| mgmt_endpoint    | Management endpoint, used for sending management commands                  |

Now, let's start our `service-mgr-agentd` daemon.

	# service service-mgr-agentd start

For more information on the command-line options of `service-mgr-agentd`, please execute the command below:

	# service-mgr-agentd --help
	
Checking the log file at `/var/log/service-mgr/service-mgr-agentd.log` should also indicate that our
`Service Manager Agent` has started successfully or contain errors if something went wrong.

## Service Manager Client

The `service-mgr-client` is the client application of `Service Manager`.

It is used for sending out service requests to `Service Manager`.

The `service-mgr-client` is the one which initiates the message flow by requesting for a
service request id from `Service Manager`. The `Service Manager daemon` replies to the client
with a unique service request id and a port number of the `Service Manager Result Publisher`.

It is the `service-mgr-client` responsibility to subscribe for messages on the `Result Publisher`,
with the request id used as the topic, so that any result messages can be received.

When we send a service request to our Agents we also include a special field in the message - a *topic*.

The *topic* name specifies to which nodes in our UNIX/Linux clusters this message was meant for.

By using a topic such as *FreeBSD* for example we would send a message to all FreeBSD nodes in our cluster,
or we can send a message with topic *Linux* which will be received by all Linux systems.

This allows us to group hosts based on certain characteristics, such as the Operating System, version, etc.

We can also send a message to a specific node only as well. We will see how this works later in the example sections.

## Example usage

In this section we will see an example usage of the `Service Manager` and how to take control over
the services on your UNIX/Linux clusters.

## Discovering Service Manager Agent nodes

The very first example shows how you can discover the nodes which are under `Service Manager` control.

We discover the nodes by sending a dummy request to all nodes for a service that doesn't really exists.
All nodes will receive this request and report back to us.

As the message topic we use the special topic *any*, so that the request is received by all nodes.

Let's see what systems we have in our cluster.

	$ service-mgr-client -e tcp://localhost:5500 -T any -c status -s dummy
	[
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "debian-dev", 
				"returncode": 1, 
				"service": "dummy", 
				"stdout": "", 
				"system": "Linux", 
				"version": "#1 SMP Debian 3.2.51-1", 
				"stderr": "dummy: unrecognized service\n"
			}, 
			"uuid": "75375cec60854df1b86888b5342bd0a9"
		}, 
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "fbsd-dev", 
				"returncode": 1, 
				"service": "dummy", 
				"stdout": "dummy does not exist in /etc/rc.d or the local startup\ndirectories (/usr/local/etc/rc.d)\n", 
				"system": "FreeBSD", 
				"version": "FreeBSD 9.2-RELEASE #0 r255898: Thu Sep 26 22:50:31 UTC 2013     root@bake.isc.freebsd.org:/usr/obj/usr/src/sys/GENERIC", 
				"stderr": ""
			}, 
			"uuid": "75375cec60854df1b86888b5342bd0a9"
		}, 
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "centos-dev", 
				"returncode": 1, 
				"service": "dummy", 
				"stdout": "", 
				"system": "Linux", 
				"version": "#1 SMP Fri Nov 22 03:15:09 UTC 2013", 
				"stderr": "dummy: unrecognized service\n"
			}, 
			"uuid": "75375cec60854df1b86888b5342bd0a9"
		}
	]

The output above shows us we have three systems connected to `Service Manager` - one FreeBSD system and two GNU/Linux systems.

In the next section we will see how to manage the services on our nodes.

## Getting service status information

Let's check the status of `sshd(8)` service on our FreeBSD nodes.

	$ service-mgr-client -e tcp://localhost:5500 -T FreeBSD -c status -s sshd
	[
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "fbsd-dev", 
				"returncode": 0, 
				"service": "sshd", 
				"stdout": "sshd is running as pid 1768.\n", 
				"system": "FreeBSD", 
				"version": "FreeBSD 9.2-RELEASE #0 r255898: Thu Sep 26 22:50:31 UTC 2013     root@bake.isc.freebsd.org:/usr/obj/usr/src/sys/GENERIC", 
				"stderr": ""
			}, 
			"uuid": "f569796669df4bf6982dd14c704900a0"
		}
	]

Every agent that runs on FreeBSD will receive the message and process the service request.

Okay, let's see how `cron(8)` is on our Linux nodes. The message topic we use this time is set to `Linux`.

	$ service-mgr-client -e tcp://localhost:5500 -T Linux -c status -s cron
	[
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "centos-dev", 
				"returncode": 1, 
				"service": "cron", 
				"stdout": "", 
				"system": "Linux", 
				"version": "#1 SMP Fri Nov 22 03:15:09 UTC 2013", 
				"stderr": "cron: unrecognized service\n"
			}, 
			"uuid": "7e7d09d85f944f98b69a2ce945eb17d1"
		}, 
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "debian-dev", 
				"returncode": 0, 
				"service": "cron", 
				"stdout": "cron is running.\n", 
				"system": "Linux", 
				"version": "#1 SMP Debian 3.2.51-1", 
				"stderr": ""
			}, 
			"uuid": "7e7d09d85f944f98b69a2ce945eb17d1"
		}
	]

From the output above see that one of our Linux nodes reported `cron: unrecognized service`.

Under RHEL/CentOS systems the `cron(8)` service name is `crond` unline `cron` as found under Debian and FreeBSD systems.

Okay, lets send this time a request directly to our CentOS system only. The message topic we use this time is `centos-dev` -- the node's hostname.

	service-mgr-client -e tcp://localhost:5500 -T centos-dev -c status -s crond
	[
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "centos-dev", 
				"returncode": 0, 
				"service": "crond", 
				"stdout": "crond (pid  1069) is running...\n", 
				"system": "Linux", 
				"version": "#1 SMP Fri Nov 22 03:15:09 UTC 2013", 
				"stderr": ""
			}, 
			"uuid": "e89a6a28435f4860b7db08de3994aabe"
		}
	]

Great, `cron(8)` is running on our CentOS node as well.

## Stopping and starting services

Now, let's stop some services from our cluster.

Here is an example command that will stop the SSH daemon on our FreeBSD nodes:

	$ service-mgr-client -e tcp://localhost:5500 -T FreeBSD -c stop -s sshd
	[
		{
			"msg": "Executed service stop request", 
			"result": {
				"node": "fbsd-dev", 
				"returncode": 0, 
				"service": "sshd", 
				"stdout": "Stopping sshd.\n", 
				"system": "FreeBSD", 
				"version": "FreeBSD 9.2-RELEASE #0 r255898: Thu Sep 26 22:50:31 UTC 2013     root@bake.isc.freebsd.org:/usr/obj/usr/src/sys/GENERIC", 
				"stderr": ""
			}, 
			"uuid": "420f22ca2cab42c6913c3b9155217c52"
		}
	]

Okay, `sshd(8)` is stopping. Let's check the status now:

	$ service-mgr-client -e tcp://localhost:5500 -T FreeBSD -c status -s sshd
	[
		{
			"msg": "Executed service status request", 
			"result": {
				"node": "fbsd-dev", 
				"returncode": 1, 
				"service": "sshd", 
				"stdout": "sshd is not running.\n", 
				"system": "FreeBSD", 
				"version": "FreeBSD 9.2-RELEASE #0 r255898: Thu Sep 26 22:50:31 UTC 2013     root@bake.isc.freebsd.org:/usr/obj/usr/src/sys/GENERIC", 
				"stderr": ""
			}, 
			"uuid": "53ac926356fa45d6afb3459682079451"
		}
	]

We can see that SSH is down, and if we try to login to the system using SSH we would verify that our way to the system is cut off.

Now, if we were working on a remote system and that happens we would have no way to get access to that system anymore. Luckily for us
`Service Manager` can still help us here and get the service up and running.

Let's start SSH back, so we can login to the system again.

	$ service-mgr-client -e tcp://localhost:5500 -T FreeBSD -c start -s ssh
	[
		{
			"msg": "Executed service start request", 
			"result": {
				"node": "fbsd-dev", 
				"returncode": 0, 
				"service": "sshd", 
				"stdout": "Performing sanity check on sshd configuration.\nStarting sshd.\n", 
				"system": "FreeBSD", 
				"version": "FreeBSD 9.2-RELEASE #0 r255898: Thu Sep 26 22:50:31 UTC 2013     root@bake.isc.freebsd.org:/usr/obj/usr/src/sys/GENERIC", 
				"stderr": ""
			}, 
			"uuid": "aa938f1447de44ec8464d6d8c0733e4e"
		}
	]

Great, `sshd(8)` is back online and we can login to it.

These examples are just one of the many where `Service Manager` can really help us in managing our cluster services.

## Handling slow services and high latency issues

Suppose we have a service that requires a bit more time to reply or we experience high latency issues.

What would happen in this situation is that the `Service Manager Client` application will send a request
to `Service Manager` and wait for a given period of time for results to be published. If there are no
results after that period of time it will simply return and there would be no results to be displayed from
our `Service Manager Agents`.

The solution to this problem is to give the `Service Manager Client` more time to wait for results to be
published. We can specify the time we wait for results in seconds from the `Result Publisher`
by using the `-w` switch of `service-mgr-client`, e.g.

	$ service-mgr-client -w 5 -e tcp://localhost:5500 -T FreeBSD -c status -s sshd

This would cause the `Service Manager Client` to wait for 5 seconds for any results to be published
on the `Result Publisher` socket of `Service Manager`. After that period it would simply return and
display the results that were published.

## Bugs

Probably. If you experience a bug issue, please report it to the
[service-mgr issue tracker on Github](https://github.com/dnaeon/async-service-mgr/issues).
