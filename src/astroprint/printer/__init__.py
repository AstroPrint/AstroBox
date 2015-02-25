# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util.comm as comm
from octoprint.settings import settings

class Printer():
	driverName = None
	_gcodeManager = None

	@staticmethod
	def getConnectionOptions():
		"""
		 Retrieves the available ports, baudrates, prefered port and baudrate for connecting to the printer.
		"""
		return {
			"ports": comm.serialList(),
			"baudrates": comm.baudrateList(),
			"portPreference": settings().get(["serial", "port"]),
			"baudratePreference": settings().getInt(["serial", "baudrate"]),
			"autoconnect": settings().getBoolean(["serial", "autoconnect"])
		}

	def __init__(self, gcodeManager):
		pass

	def connect(self, port=None, baudrate=None):
		pass

	def disconnect(self):
		pass

	def getCurrentConnection(self):
		pass

	def isPaused(self):
		pass

	def isPrinting(self):
		pass