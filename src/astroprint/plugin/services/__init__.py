# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging

class PluginService(object):
	_validEvents = []

	def __init__(self):
		self._eventSubscribers = {}
		self._logger = logging.getLogger('PluginService::%s' % self.__class__.__name__)

	# Subscribe to a service event(s)
	#
	# - events: the event name or an array of event names
	# - callback: The handler for the event. It will receive the following parameters:
	#					- event: Event namd
	#					- data: a hash with data (defined per event)
	def subscribe(self, events, callback):
		if isinstance(events, basestring):
			events = [events]

		for e in events:
			if e in self._validEvents:
				if e in self._eventSubscribers:
					if callback not in self._eventSubscribers[e]:
						self._eventSubscribers[e].add(callback)
				else:
					self._eventSubscribers[e] = set([callback])

	# Unsubscribe from a service event
	#
	# - events: the event name or an array of event names
	# - callback: the callback used when registering.
	def unsubscribe(self, events, callback):
		if isinstance(events, basestring):
			events = [events]

		for e in events:
			if e in self._eventSubscribers:
				#discard does not raise if the element doesn't exist
				self._eventSubscribers[e].discard(callback)
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
				for h in handlers:
					try:
						h(event, data)
					except:
						self._logger.error('Problem publishing event', exc_info= True)
