# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def printerProfileManager():
	global _instance
	if _instance is None:
		_instance = PrinterProfileManager()
	return _instance

import os
import yaml
import logging
import shutil

from octoprint.settings import settings
from astroprint.plugin import pluginManager

class PrinterProfileManager(object):
	def __init__(self):
		self._settings = settings()

		configDir = self._settings.getConfigFolder()

		self._infoFile = "%s/printer-profile.yaml" % configDir
		self._logger = logging.getLogger(__name__)

		self.data = {
			'driver': "marlin",
			'plugin': None,
			'extruder_count': 1,
			'max_nozzle_temp': 280,
			'max_bed_temp': 140,
			'heated_bed': True,
			'cancel_gcode': ['G28 X0 Y0'],
			'invert_z': False
		}

		if not os.path.isfile(self._infoFile):
			factoryFile = "%s/printer-profile.factory" % configDir
			if os.path.isfile(factoryFile):
				shutil.copy(factoryFile, self._infoFile)
			else:
				open(self._infoFile, 'w').close()

		if self._infoFile:
			config = None
			with open(self._infoFile, "r") as f:
				config = yaml.safe_load(f)

			def merge_dict(a,b):
				for key in b:
					if isinstance(b[key], dict):
						merge_dict(a[key], b[key])
					else:
						a[key] = b[key]

			if config:
				merge_dict(self.data, config)

	def save(self):
		with open(self._infoFile, "wb") as infoFile:
			yaml.safe_dump(self.data, infoFile, default_flow_style=False, indent="    ", allow_unicode=True)

	def set(self, changes):
		for k in changes:
			if k in self.data:
				if self.data[k] != changes[k]:
					if k == 'driver':
						#change printer object
						from astroprint.printer.manager import printerManager

						try:
							printerManager(changes['driver'])

						except Exception as e:
							self._logger.error("Error selecting driver %s: %s" % (changes['driver'], e))
							#revent to previous driver
							printerManager(self.data['driver'])
							raise e

					self.data[k] = self._clean(k, changes[k])
			else:
				self._logger.error("trying to set unkonwn printer profile field %s to %s" % (k, str(changes[k])))

	def driverChoices(self):
		plugins = pluginManager().getPluginsByProvider('printerComms')

		result = { ("plugin:%s" % k) : { 'name': plugins[k].definition['name'], 'properties': plugins[k].settingsProperties } for k in plugins }

		result.update({
			'marlin': {'name': 'GCODE - Marlin / Repetier Firmware', 'properties': {'customCancelCommands': True}},
			's3g': {'name': 'X3G - Sailfish / Makerbot Firmware',  'properties': {'customCancelCommands': False}}
		})

		return result

	def _clean(self, field, value):
		if field in ['extruder_count', 'max_nozzle_temp', 'max_bed_temp']:
			return int(value)
		elif field == 'heated_bed':
			return bool(value)
		else:
			return value
