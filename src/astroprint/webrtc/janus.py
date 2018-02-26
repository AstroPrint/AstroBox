# This library was originally started from code at https://github.com/mayfieldrobotics/janus-py/blob/c84d9f6912d5a11db14315a750d580a75d34b15e/janus.py

"""
Client library for interfaceing w/ a Janus gateway using these three types:

- `Session`
- `Janus`
- `KeepAlive`

Typical usage is to create a representation of your Janus `Plugin`:

.. code:: python

		class MyPlugin(janus.Plugin):

				name = 'janus.plugin.krazyeyezkilla'

				def sup(self, greets)
						self.send_message({'wat': greets})


		my_plugin = MyPlugin()

setup a session:

.. code:: python

		session = janus.Session('ws://127.0.0.1', secret='janusrocks')
		session.register_plugin(my_plugin)

keep it alive:

.. code:: python

		session_ka = janus.KeepAlive(session)
		session_ka.daemon = True
		session_ka.start()

and then use your plugin:

.. code:: python

		my_plugin.sup('dawg')

"""
import functools
import json
import logging
import os
import pprint
import random
import select
import socket
import string
import threading
import time

import blinker
import concurrent.futures
import ws4py.client.threadedclient


__version__ = '0.1.0'

__all__ = [
		'Connection',
		'Session',
		'Plugin',
]

logger = logging.getLogger(__name__)


class Connection(object):
		"""
		Connection to a Janus gateway whose *type* is determined by a url scheme:

		- ws://
		- wss://
		- http://
		...

		which can also be used to specify an async mechanism:

		- ws+thread://
		- ws+process://
		- ws+gevent://
		...

		Use it like e.g.:

		.. code:: python

				cxn = Connection('ws://127.0.0.1')

				def connection_opened(cxn):
						print "connected!"

				def connection_opened(cxn):
						print "disconnected!"

				def connection_message(cxn, message):
						print message

				on_opened.connect(connection_opened, sender=cxn)
				on_closed.connect(connection_closed, sender=cxn)
				on_message.connect(connection_message, sender=cxn)

		but typically you'll just use `Session` instead.

		"""

		class ThreadedWebSocketClient(ws4py.client.threadedclient.WebSocketClient):

				def __init__(self, parent, *args, **kwargs):
						self.parent = parent
						kwargs['protocols'] = ['janus-protocol']
						super(Connection.ThreadedWebSocketClient, self).__init__(
								*args, **kwargs
						)

				# ws4py.client.threadedclient.WebSocketClient

				def opened(self):
						self.parent.on_opened.send(self.parent)

				def closed(self, code, reason=None):
						self.parent.on_closed.send(self.parent, code=code, reason=reason)

				def received_message(self, message):
						self.parent.on_message.send(self.parent, message=message)

		@classmethod
		def client_type(cls, url):
				if url.startswith('ws://'):
						return cls.ThreadedWebSocketClient
				if url.startswith('wss://'):
						return cls.ThreadedWebSocketClient
				raise ValueError('No client for url "{0}"'.format(url))

		def __init__(self, url, *args, **kwargs):
				self.url = url
				self.cli = self.client_type(url)(self, url, *args, **kwargs)

		# Signal fired when `Connection` has been established.
		on_opened = blinker.Signal()

		# Signal fired when `Connection` has been closed.
		on_closed = blinker.Signal()

		# Signal fired when `Connection` receives a message
		on_message = blinker.Signal()


class Session(object):
		"""
		Manages a `Connection` to a Janus gateway.
		"""

		# State indicating session has been disconnected.
		DISCONNECTED = 'disconnected'

		# State indicating session is connecting.
		CONNECTING = 'connecting'

		# State indicating session has been connected.
		CONNECTED = 'connected'

		def __init__(self, url, secret=None, cxn_cls=Connection, **kwargs):
				self.url = url
				self.secret = secret
				self.state = self.DISCONNECTED
				self.cxn_cls = cxn_cls
				self.cxn = None
				self.cxn_kwargs = kwargs
				self.cxns = 0
				self.created = threading.Event()
				self.plugins = []
				self.plugin_idx = {}
				self.txns = {}
				self.txn_q = []
				self._connected = None
				self._disconnected = None
				self._created = None

		# Signal fired when `Session` has been connected.
		on_connected = blinker.Signal()

		# Signal fired when `Session` has been disconnected.
		on_disconnected = blinker.Signal()

		# Signal fired when a `Session` level message is received.
		on_message = blinker.Signal()

		# Signal fired when a `Session` `Plugin` been attached.
		on_plugin_attached = blinker.Signal()

		# Signal fired when a `Session` `Plugin` been detached.
		on_plugin_detached = blinker.Signal()

		# Signal fired when a `Session` level message is received.

		def connect(self, timeout=None):
				if self._connected is None:
						self._connected = concurrent.futures.Future()

				if self.is_connected:
						logger.info('session already connected to %s', self.cxn.url)
				else:
						# init state
						self.id = None
						self.created.clear()
						self.plugin_idx.clear()
						for plugin in self.plugins:
								plugin.id = None
						self.state = self.CONNECTING

						# connect ...
						try:
								self.cxn = self.cxn_cls(url=self.url, **self.cxn_kwargs)
								self.cxn.on_opened.connect(
										self._on_connection_opened, sender=self.cxn
								)
								self.cxn.on_closed.connect(
										self._on_connection_closed, sender=self.cxn
								)
								self.cxn.on_message.connect(
										self._on_connection_message, sender=self.cxn
								)
								if timeout is not None:
										prev_timeout = self.cxn.cli.sock.gettimeout()
										self.cxn.cli.sock.settimeout(timeout)
								try:
										logger.debug('connecting to %s', self.url)
										self.cxn.cli.connect()
								finally:
										logger.debug('connected to %s', self.url)
										if timeout is not None:
												self.cxn.cli.sock.settimeout(prev_timeout)
						except socket.error, ex:
								# reset state
								self.state = self.DISCONNECTED
								self.cxn = None
								self._connected.set_exception(ex)
								raise

				return self._connected

		def disconnect(self):
				if self._disconnected is None:
						self._disconnected = concurrent.futures.Future()

				if self.is_connected:
						self.send_message({'janus': 'destroy'})
				if self.is_disconnected:
						self._disconnected.set_result(self)
				else:
						logger.debug('disconnecting from %s', self.url)
						self.cxn.cli.close()

				return self._disconnected

		@property
		def is_connecting(self):
				return self.state == self.CONNECTING

		@property
		def is_connected(self):
				return self.state == self.CONNECTED

		@property
		def is_disconnected(self):
				return self.state == self.DISCONNECTED

		def create(self):
				if self._created is None:
						self._created = concurrent.futures.Future()
				if self.is_created:
						logger.info('session for %s w/ id %s already created', self.cxn.url, self.id)
				else:
						cb = functools.partial(self._on_create_done)
						f = self.send_message({'janus': 'create'})
						f.add_done_callback(cb)
				return self._created

		def _on_create_done(self, f):

				def _attached_plugin(future):
						plugin = future.result()
						pending.remove(plugin)
						if not pending:
								self._created.set_result(self)
						self._drain_txn_q()

				message = f.result()
				logger.info('created session w/ id %s', message['id'])
				self.id = message['id']
				pending = self.plugins[:]
				for plugin in self.plugins:
						f = self._attach_plugin(plugin)
						f.add_done_callback(_attached_plugin)

		@property
		def is_created(self):
				return self.is_connected and self.id is not None

		def register_plugin(self, plugin):
				if plugin.is_attached:
						raise ValueError('Plugin {0} is already attached'.format(plugin.id))
				self.plugins.append(plugin)

		def unregister_plugin(self, plugin):
				self.plugin_idx.pop(plugin.id, None)
				i = self.plugins.index(plugin)
				if i == -1:
						return
				plugin = self.plugins.pop(i)

		def send_message(self, message, future=None):
				if 'janus' not in message:
						req = {
								'janus': 'message',
								'body': message,
						}
				else:
						req = message
				if self.id:
						req['session_id'] = self.id
				if 'transaction' not in req:
						req['transaction'] = self._generate_txn_id()
				if self.secret:
						req['apisecret'] = self.secret
				raw = json.dumps(req, indent=4)
				f = concurrent.futures.Future() if future is None else future
				self.txns[req['transaction']] = f
				if self.is_connected:
						try:
								logger.debug('sending message:\n%s', raw)
								self.cxn.cli.send(raw, binary=False)
						except:
								self.txns.pop(req['transaction'], None)
								raise
				else:
						logger.debug(
								'Not connected, message lost w/ transaction %s:\n%s',
								req['transaction'], raw
						)
						#self.msg_q.append((req['transaction'], raw))
						if self.is_disconnected:
								self.connect()
				return f

		def send_keep_alive(self):
				if not self.is_created:
						raise RuntimeError('Session has not been created.')
				message = {
						'janus': 'keepalive',
				}
				return self.send_message(message)

		# `Plugin` events

		def _attach_plugin(self, plugin):
				message = {
						'janus': 'attach',
						'plugin': plugin.name,
				}
				attached = concurrent.futures.Future()
				f = self.send_message(message)
				cb = functools.partial(
						self._attach_plugin_done, plugin=plugin, attached=attached
				)
				f.add_done_callback(cb)
				return attached

		def _attach_plugin_done(self, future, plugin, attached=None):
				message = future.result()
				plugin_id = message['id']
				logger.info('attached plugin %s to session id %s', plugin_id, self.id)
				self.plugin_idx[plugin_id] = plugin
				plugin.attached(self, plugin_id)
				if attached:
						attached.set_result(plugin)
				self.on_plugin_attached.send(self, plugin=plugin)

		def _detach_plugin(self, plugin):
				message = {
						'janus': 'detach',
						'handle_id': plugin.id
				}
				f = self.send_message(message)
				cb = functools.partial(self._detach_plugin_done, plugin.id)
				f.add_done_callback(cb)

		def _detach_plugin_done(self, plugin_id, message):
				plugin = self.plugin_idx.pop(plugin_id, None)
				if plugin:
						plugin.detached()
				self.on_plugin_detached.send(self, plugin=plugin)

		# transactions

		_TRANSACTION_ID_ALPHABET = string.ascii_letters + string.digits

		_TRANSACTION_ID_LEN = 12

		@classmethod
		def _generate_txn_id(cls):
				return ''.join(
						random.choice(cls._TRANSACTION_ID_ALPHABET)
						for _ in range(cls._TRANSACTION_ID_LEN)
				)

		def _txn_result(self, txn_id, data):
				f = self.txns.pop(txn_id, None)
				if f is None:
						logger.info('no transaction w/ id {0}'.format(txn_id))
						return False
				f.set_result(data)
				return True

		def _txn_exception(self, txn_id, ex):
				f = self.txns.pop(txn_id, None)
				if f is None:
						logger.info('no transaction w/ id {0}'.format(txn_id))
						return False
				f.set_exception(ex)
				return True

		def _drain_txn_q(self):
				while self.txn_q:
						txn_id, raw = self.txn_q.pop()
						if txn_id in self.txns:
								logger.debug('sending message:\n%s', raw)
								self.cxn.cli.send(raw, binary=False)

		# `Connection` events

		def _on_connection_opened(self, cxn):
				if cxn is not self.cxn:
						logger.info('dropping "opened" from cxn %s != %s', cxn, self.cxn)
						return
				self.state = self.CONNECTED
				self.cxns += 1
				self._connected.set_result(self)
				self.create()

		def _on_connection_closed(self, cxn, code, reason):
				if cxn is not self.cxn:
						logger.info('dropping "closed" from cxn %s != %s', cxn, self.cxn)
						return
				self.state = self.DISCONNECTED
				self.on_disconnected.send(self)
				self.plugin_idx.clear()
				for plugin in self.plugins:
						if plugin.is_attached:
								plugin.detached()
				self.txns.clear()
				self.cxn.on_opened.disconnect(self._on_connection_opened)
				self.cxn.on_closed.connect(self._on_connection_closed)
				self.cxn.on_message.connect(self._on_connection_message)
				#self._disconnected.set_result(self)

		def _on_connection_message(self, cxn, message):
				raw = message
				if cxn is not self.cxn:
						logger.info(
								'dropping "received_message" from cxn %s != %s', cxn, self.cxn
						)
						return
				logger.debug('received message:\n%s', raw)
				try:
						message = json.loads(str(raw))
				except (TypeError, ValueError), ex:
						logger.error(
								'dropping malformed message "%s":\n%s', ex, raw, exc_info=ex
						)
						return
				if not isinstance(message, dict):
						logger.error('received non-object message:\n%s', raw)
						return
				if 'janus' not in message:
						logger.error('message is missing "janus" field:\n%s', raw)
						return
				if message['janus'] not in self._MESSAGE_HANDLERS:
						logger.error(
								'unsupported "janus" message "%s":\n%s',
								message['janus'], message
						)
						return
				self._MESSAGE_HANDLERS[message['janus']](self, message)

		# message handlers

		def _on_success_message(self, message):
				txn_id = message.get('transaction')
				plugin_id = message.get('sender')
				plugin = self.plugin_idx.get(plugin_id)
				plugindata = message.get('plugindata')
				if plugindata:
						logger.debug(
								'success from %s (plugin=%s)', plugin_id, plugindata['plugin']
						)
						data = plugindata.get('data')
				else:
						logger.debug('success from %s', plugin_id)
						data = message.get('data')
				if txn_id is not None:
						self._txn_result(txn_id, data)
				if plugin is not None:
						plugin.on_message.send(plugin, message=data)

		def _on_error_message(self, message):
				txn_id = message.get('transaction')
				code = message.get('code')
				reason = message.get('reason', 'unknown')
				logger.info('error %s (code=%s)', reason, code)
				ex = RuntimeError('{0} (code={1})'.format(reason, code))
				if txn_id is not None:
						self._txn_exception(txn_id, ex)

		def _on_keepalive_message(self, message):
				pass

		def _on_ack_message(self, message):
				pass

		def _on_webrtcup_message(self, message):
				plugin_id = message.get('sender')
				plugin = self.plugin_idx.pop(plugin_id, None)
				if plugin is None:
						logger.info('no plugin w/ id %s to webrtcup', plugin_id)
						return
				plugin.on_webrtcup.send(plugin)

		def _on_hangup_message(self, message):
				plugin_id = message.get('sender')
				plugin = self.plugin_idx.pop(plugin_id, None)
				if plugin is None:
						logger.info('no plugin w/ id %s to hangup', plugin_id)
						return
				plugin.on_hangup.send(plugin)
				plugin.detached()

		def _on_detached_message(self, message):
				plugin_id = message.get('sender')
				plugin = self.plugin_idx.pop(plugin_id, None)
				if plugin is None:
						logger.info('no plugin w/ id %s to detach', plugin_id)
						return
				plugin.detached()

		def _on_event_message(self, message):
				txn_id = message.get('transaction')
				plugin_id = message.get('sender')
				plugin = self.plugin_idx.get(plugin_id)
				plugindata = message.get('plugindata')
				jsep = message.get('jsep')
				if plugindata:
						logger.debug(
								'event from %s (plugin=%s)',
								plugin_id, plugindata['plugin']
						)
						data = plugindata.get('data')
				else:
						logger.debug('event from %s', plugin_id)
						data = message
				if jsep:
						logger.debug('... w/ sdp\n%s', jsep)
				if txn_id is not None:
						self._txn_result(txn_id, data)
				if plugin is None:
						logger.info('no plugin w/ id %s to receive message', plugin_id)
				else:
						plugin.on_message.send(plugin, message=data, sdp=jsep)

		def _on_media_message(self, message):
				pass

		_MESSAGE_HANDLERS = {
				'success': _on_success_message,
				'error': _on_error_message,
				'keepalive': _on_keepalive_message,
				'ack': _on_ack_message,
				'webrtcup': _on_webrtcup_message,
				'hangup': _on_hangup_message,
				'detached': _on_detached_message,
				'event': _on_event_message,
				'media': _on_media_message,
		}


class Plugin(object):
		"""
		Interace to Janus `Session` plugin for you to inherit. Use it like e.g.:

		.. code:: python

				class MyPlugin(janus.Plugin):

						name = 'janus.plugin.mine'

						def my_command(self, some_arg)
								self.send_message({'some_arg': some_arg })


				my_plugin  = MyPlugin()

				session = janus.Session('ws://127.0.0.1')
				session.register_plugin(my_plugin)

				session.connect()

		"""

		# Name of the plugin. Its typically a class attribute assigned by your
		# `Plugin` class.
		name = None

		# Handle id of the plugin. This will be set on `Plugin.attached` and reset
		# on `Plugin.detached`.
		id = None

		# Session description for local media. This will be set by
		# `Plugin.set_session_description` and reset on `Plugin.detached`.
		sdp = None

		# Flag indicating whether or no `Plugn.sdp` has been sent to Janus.
		sdp_sent = False

		# `Session` this plugin is attached to. This will be set on
		# `Plugin.attached` and reset on `Plugin.detached`.
		session = None

		# Signal fired when a `Plugin` is attached to a `Session`.
		on_attached = blinker.Signal()

		# Signal fired when a `Plugin` is attached to a `Session`.
		on_detached = blinker.Signal()

		# Signal fired when a `Plugin` receives a message.
		on_message = blinker.Signal()

		# Signal fired when webrtc for a `Plugin` has been setup.
		on_webrtcup = blinker.Signal()

		# Signal fired when webrtc session for a `Plugin` has been torn down.
		on_hangup = blinker.Signal()

		def __init__(self):
				self.txn_q = []

		def attached(self, session, id):
				self.session = session
				self.id = id
				self.sdp = None
				self.sdp_sent = False
				self.on_attached.send(self)

		def detached(self):
				self.session = None
				self.id = None
				self.sdp = None
				self.sdp_sent = False
				self.on_detached.send(self)

		@property
		def is_attached(self):
				return self.session is not None and self.id is not None

		def send_message(self, message):
				if 'janus' not in message:
						req = {
								'janus': 'message',
								'body': message,
						}
				else:
						req = message
				if self.id:
						req['handle_id'] = self.id
				if not self.is_attached:
						f = concurrent.futures.Future()
						self.txn_q.append((req, f))
				else:
						if req['janus'] == 'message' and self.sdp and not self.sdp_sent:
								req['jsep'] = self.sdp
						f = self.session.send_message(req)
						if 'jsep' in req:
								self.sdp_sent = True
				return f

		def set_session_description(self, type, sdp):
			if self.sdp:
				raise RuntimeError(
					'sdp already set to:\n%s', pprint.pformat(self.sdp)
				)

			self.sdp = {
				'type': type,
				'sdp': sdp,
			}

		def add_ice_candidate(self, candidate, sdp_mid, sdp_mline_index):
				message = {
						'janus': 'trickle',
						'candidate': {
								'candidate': candidate,
								'sdpMid': sdp_mid,
								'sdpMLineIndex': sdp_mline_index,
						},
				}
				return self.send_message(message)

		def hangup(self):
				message = {
						'janus': 'hangup'
				}
				return self.send_message(message)

		def _drain_txn_q(self):
				while self.txn_q:
						req, f = self.txn_q.pop()
						if req['janus'] == 'message' and self.sdp and not self.sdp_sent:
								req['jsep'] = self.sdp
						self.session.send_message(req, future=f)
						if 'jsep' in req:
								self.sdp_sent = True


class Event(object):
		"""
		Pipe backed event.

		http://lat.sk/2015/02/passive-waiting-on-multiple-events-in-python-3-select/
		"""

		def __init__(self):
				self._rfd, self._wfd = os.pipe()

		def __del__(self):
				os.close(self._rfd)
				os.close(self._wfd)

		@classmethod
		def any(cls, events, timeout=None):
				rfds, _, _ = select.select([e._rfd for e in events], [], [], timeout)
				return [e for e in events if e._rfd in rfds][0] if rfds else None

		# threading.Event

		def wait(self, timeout=None):
				rfds, _, _ = select.select([self._rfd], [], [], timeout)
				return self._rfd in rfds

		def is_set(self):
				return self.wait(0)

		def isSet(self):
				return self.is_set()

		def clear(self):
				if self.is_set():
						os.read(self._rfd, 1)

		def set(self):
				if not self.is_set():
						os.write(self._wfd, b'1')

		# file-like

		def fileno(self):
				return self._rfd


class KeepAlive(threading.Thread):
		"""
		Helper used to keep a `Session` connected to the Janus gateway which is
		does by:

		- Periodically sending "keep-alive" messages to the gateway when connected.
		- Re-connecting when `Session.is_disconnected`

		Use it like e.g.:

		.. code:: python

				ka = janus.KeepAlive(session)
				ka.daemon = True
				ka.start()

				...

				ka.stop()
				ka.join(10.0)
				if ka.is_stopped:
						print "didn't gracefully stop w/in 10.0 secs"

		"""

		# Number of seconds between keep alive message sent to `Session`.
		beat_period = 20

		# Number of seconds before giving up on a connection attempt.
		connect_timeout = 60

		# Initial number of seconds to wait before attempting to reconnect.
		init_reconnect_timeout = 1

		# Maximum number of seconds to wait before attempting to reconnect.
		max_reconnect_timeout = 60

		# Maximum number of seconds to wait for keep alive to be resumed.
		resumed_timeout = 10

		# Number of seconds to wait when idle.
		idle_timeout = 1

		def __init__(self, session, *args, **kwargs):
				threading.Thread.__init__(self, *args, **kwargs)
				self.session = session
				self.stop_evt = Event()
				self.resume_evt = Event()
				self.resume_evt.set()
				self.session.on_connected.connect(
						self._on_connected, sender=self.session
				)
				self.session.on_disconnected.connect(
						self._on_disconnected, sender=self.session
				)
				self.connect_at = 0
				self.reconnect_timeout = self.init_reconnect_timeout
				self.beat_at = time.time()

		def pause(self):
				self.resume_evt.clear()

		@property
		def is_paused(self):
				return not self.resume_evt.is_set()

		def resume(self):
				self.resume_evt.set()

		def stop(self):
				self.stop_evt.set()

		@property
		def is_stopped(self):
				return not self.is_alive()

		# threading.Thread

		def run(self):
				logger.debug('running keep-alive for %s', self.session)

				while not self.stop_evt.is_set():
						now = time.time()

						if self.is_paused:
								logger.debug(
										'waiting %0.4f sec(s) for resume', self.resumed_timeout,
								)
								Event.any(
										[self.stop_evt, self.resume_evt],
										self.resumed_timeout
								)
								continue

						if self.session.is_disconnected:
								if self.connect_at > now:
										delay = self.connect_at - now
										logger.debug(
												'waiting %0.4f sec(s) before reconnect', delay
										)
										if self.stop_evt.wait(delay):
												continue
								if self.session.is_disconnected:
										try:
												logger.debug('keep-alive %s connecting', self.session)
												self.session.connect(timeout=2.0)
										except Exception:
												logger.exception(
														'connection failed, will attempt again in %0.4f '
														'sec(s)', self.reconnect_timeout
												)
												self.connect_at = time.time() + self.reconnect_timeout
												self.reconnect_timeout = min(
														self.reconnect_timeout * 2,
														self.max_reconnect_timeout
												)
												continue
										continue

						if self.session.is_connected:
								if now < self.beat_at:
										delay = self.beat_at - now
										logger.debug(
												'waiting %0.4f sec(s) before sending keep alive', delay
										)
										if self.stop_evt.wait(delay):
												continue
								if self.session.is_created:
										self.session.send_keep_alive()
										self.beat_at = time.time() + self.beat_period
								continue

						logger.debug('idling for %0.4f sec(s)', self.idle_timeout)
						self.stop_evt.wait(self.idle_timeout)

				logger.debug('exiting keep-alive for %s', self.session)

		# `Session` events

		def _on_connected(self, session):
				self.reconnect_timeout = self.init_reconnect_timeout
				self.beat_at = 0

		def _on_disconnected(self, session):
				self.reconnect_timeout = self.init_reconnect_timeout
