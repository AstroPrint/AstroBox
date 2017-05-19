# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from octoprint.settings import settings

# singleton
_instance = None

# This object is recreated when the driver is changed in the printer profile page.
# DO NOT store a reference to the result of printerManager in any persistant object.

DEFAULT_MANAGER = 'marlin'

def printerManager(driver = None):
	global _instance

	transferredCallbacks = None

	if driver is not None and _instance is not None and _instance.driverName != driver:
		transferredCallbacks = _instance.registeredCallbacks

		#reset port and baud settings
		s = settings()
		s.set(['serial', 'port'], None)
		s.set(['serial', 'baudrate'], None)

		_instance.rampdown()
		_instance = None

	if _instance is None and driver:

		if driver.startswith('plugin:'):
			from astroprint.printer.plugin import PrinterWithPlugin, NoPluginException

			try:
				_instance = PrinterWithPlugin(driver[7:])

			except NoPluginException:
				#The plugin is gone. Pick the default
				from astroprint.printerprofile import printerProfileManager
				ppm = printerProfileManager()
				ppm.set({'driver': DEFAULT_MANAGER})
				ppm.save()

		else:
			import importlib

			classInfo = {
				'marlin': ('.marlin', 'PrinterMarlin'),
				's3g': ('.s3g', 'PrinterS3g')
			}[driver]

			module = importlib.import_module(classInfo[0], 'astroprint.printer')
			_instance = getattr(module, classInfo[1])()

		if _instance:
			#transfer callbacks if any
			if transferredCallbacks:
				_instance.registeredCallbacks = transferredCallbacks

	return _instance
