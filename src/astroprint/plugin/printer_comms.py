# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

class PrinterCommsService(object):

	## Implement these functions


	#
	# Returns a hash with the following members:
	#
	# customCancelCommands: Whether the driver support custom GCODE to be send when canceling a print job
	#

	@property
	def properties(self):
		raise NotImplementedError()
