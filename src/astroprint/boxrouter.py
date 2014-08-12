# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import socket
import asynchat
import asyncore
import threading

from octoprint.settings import settings

class AstroprintBoxRouter(asynchat.async_chat):
	def __init__(self):
		asynchat.async_chat.__init__(self)
		self._ibuffer = []
		self.set_terminator("\n")
		self._settings = settings()

		addr = self._settings .get(['cloudSlicer','boxrouter'])

		if ":" in addr:
			addr = addr.split(':')
			self._address = addr[0]
			self._port = int(addr[1])
		else:
			self._address = addr
			self._port = 80

		self.boxrouter_connect()

		self._listener = threading.Thread(target=asyncore.loop)
		self._listener.daemon = True
		self._listener.start()

	def boxrouter_connect(self):
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect( (self._address, self._port) )
		self.connected = True

		self.push(json.dumps({
			'msg': 'auth',
			'data': {
				'email': self._settings .get(['cloudSlicer', 'email']),
				'privateKey': self._settings .get(['cloudSlicer', 'privateKey'])
			}
		}))

	def handle_connect(self):
		pass

	def handle_close(self):
		print 'remote closed'
		self.close()
		self.connected = False

	def collect_incoming_data(self, data):
		self._ibuffer.append(data)

	def found_terminator(self):
		self.onMessage()
		self._ibuffer = []

	def onMessage(self):
		for msg in self._ibuffer:
			print msg