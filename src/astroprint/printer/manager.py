# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

# This object is recreated when the driver is changed in the printer profile page.
# DO NOT store a reference to the result of printerManager in any persistant object.

def printerManager(driver = None):
	global _instance

	if driver is not None and _instance is not None and _instance.driverName != driver:
		_instance.rampdown()
		_instance = None

	if _instance is None and driver:
		import importlib

		if driver.startswith('plugin:'):
			from astroprint.printer.plugin import PrinterWithPlugin
			_instance = PrinterWithPlugin(driver[7:])

		else:
			classInfo = {
				'marlin': ('.marlin', 'PrinterMarlin'),
				's3g': ('.s3g', 'PrinterS3g')
			}[driver]

			module = importlib.import_module(classInfo[0], 'astroprint.printer')
			_instance = getattr(module, classInfo[1])()

	return _instance
