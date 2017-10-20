# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

#
# Base class for transport objects
#

class PrinterCommTransport(object):
	#
	# Constructor. eventListener needs to implement the TransportEvents Interface
	#
	def __init__(self, eventListener):
		self._eventListener = eventListener

	#
	# Opens the communications link
	#
	# Parameters depend on the implementation
	#
	# Returns (boolean): True is succesful or False if not
	#
	def openLink(self, **kwargs):
		raise NotImplementedError()

	#
	# Closes the communications link
	#
	def closeLink(self):
		raise NotImplementedError()

	#
	# Writes data into the transport layer
	#
	# data: the data to write
	#	completed: an optiona callback function that indicates the write was done
	#
	def write(self, data, completed= None):
		raise NotImplementedError()

	#
	# Check whether the transport link is open for communications
	#
	@property
	def isLinkOpen(self):
		raise NotImplementedError()

	#
	# Check whether the transport link is able to send/receive data
	#
	@property
	def canTransmit(self):
		raise NotImplementedError()

	#
	# Returns a tuple with the settings used for the active connection (port, baudrate)
	#
	# baudrate is optional and can be None, port is None is no connection is active
	#
	@property
	def connSettings(self):
		raise NotImplementedError()


#
# Interface class for transport events
#

class TransportEvents(object):
	#
	# The communications link is open
	#
	def onLinkOpened(self):
		pass

	#
	# The communications link is closed
	#
	def onLinkClosed(self):
		pass

	#
	# Data was received on the link
	#
	def onDataReceived(self, data):
		pass

	#
	# There was an error on the link
	#
	def onLinkError(self, error, description=None):
		pass

	#
	# Something non critical happened on the line
	#
	def onLinkInfo(self, info):
		pass
