# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import weakref
import logging
import json

from astroprint.boxrouter.handlers.requesthandler import RequestHandler

class BoxRouterMessageHandler(object):
	def __init__(self, weakRefBoxRouter, wsClient):
		self._weakRefBoxRouter = weakRefBoxRouter
		self._weakWs = weakref.ref(wsClient)
		self._logger = logging.getLogger(__name__)
		self._subscribers = 0

	def auth(self, msg):
		router = self._weakRefBoxRouter()
		if router:
			return router.processAuthenticate(msg['data'] if 'data' in msg else None)
		else:
			return None

	def set_temp(self, msg):
		from astroprint.printer.manager import printerManager

		printer = printerManager()

		if printer.isOperational():
			payload = msg['payload']
			printer.setTemperature(payload['target'] or 0.0, payload['value'] or 0.0)

		return None

	def update_subscribers(self, msg):
		wsClient = self._weakWs()

		if wsClient:
			self._subscribers += int(msg['data'])

			if self._subscribers > 0:
				wsClient.registerEvents()
			else:
				self._subscribers = 0
				wsClient.unregisterEvents()

		return None

	def request(self, msg):
		wsClient = self._weakWs()

		if wsClient:
			handler = RequestHandler(wsClient._printerListener)

			try:
				reqId = msg['reqId']
				clientId = msg['clientId']
				request = msg['data']['type']
				data = msg['data']['payload']

				method  = getattr(handler, request, None)
				if method:
					response = method(data, clientId)
					if response is None:
						response = {'success': True}

				else:
					response = {
						'error': True,
						'message': 'This Box does not recognize the request type [%s]' % request
					}

				wsClient.send(json.dumps({
					'type': 'req_response',
					'reqId': reqId,
					'data': response
				}))

			except Exception as e:
				message = 'Error sending [%s] response: %s' % (request, e)
				self._logger.error( message )
				wsClient.send(json.dumps({
					'type': 'req_response',
					'reqId': reqId,
					'data': {'error': True, 'message': message }
				}))
