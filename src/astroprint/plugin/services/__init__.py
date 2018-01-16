# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import time

from octoprint.events import eventManager

class PluginService(object):
	_validEvents = []

	def __init__(self):
		self._eventSubscribers = {}
		self._logger = logging.getLogger('PluginService::%s' % self.__class__.__name__)
		self._eventManager = eventManager()

	# Subscribe to a service event(s)
	#
	# - events: the event name or an array of event names
	# - callback: The handler for the event. It will receive the following parameters:
	#					- event: Event name
	#					- data: a hash with data (defined per event)
	def subscribe(self, events, callback, freq=0.0):
		if isinstance(events, basestring):
			events = [events]

		for e in events:
			if e in self._validEvents:
				if e in self._eventSubscribers:
					if callback not in self._eventSubscribers[e]:
						self._eventSubscribers[e][callback] = [freq, None]
				else:
					self._eventSubscribers[e] = { callback: [freq, None] }

	# Unsubscribe from a service event
	#
	# - events: the event name or an array of event names
	# - callback: the callback used when registering.
	def unsubscribe(self, events, callback):
		if isinstance(events, basestring):
			events = [events]

		for e in events:
			if e in self._eventSubscribers and callback in self._eventSubscribers[e]:
				#discard does not raise if the element doesn't exist
				del self._eventSubscribers[e][callback]

				if not bool(self._eventSubscribers[e]):
					del self._eventSubscribers[e]

	# Publish an event to subscribers
	#
	# - event: Event name
	# - data: Data to be passed to the event
	def publishEvent(self, event, data= None):
		if event in self._validEvents:
			handlers = self._eventSubscribers.get(event)
			if handlers:
				now = time.time()
				for cb in handlers.keys():
					handler = handlers[cb]
					freq = handler[0]
					last = handler[1]
					if last is None or now - last >= freq:
						try:
							handler[1] = now
							cb(event, data)
						except:
							self._logger.error('Problem publishing event: %s' % event, exc_info= True)
