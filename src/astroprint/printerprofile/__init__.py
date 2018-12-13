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
import uuid

from octoprint.settings import settings

from astroprint.plugin import pluginManager
from astroprint.util import merge_dict
from astroprint.manufacturerpkg import manufacturerPkgManager
from astroprint.cloud import astroprintCloud, AstroPrintCloudNoConnectionException

class PrinterProfileManager(object):
	def __init__(self):
		self._settings = settings()

		configDir = self._settings.getConfigFolder()

		self._infoFile = "%s/printer-profile.yaml" % configDir
		self._logger = logging.getLogger(__name__)
		self.data = {
			'last_definition_version': None,
			'driver': "marlin",
			'plugin': None,
			'extruder_count': 1,
			'max_nozzle_temp': 280,
			'max_bed_temp': 140,
			'heated_bed': True,
			'cancel_gcode': ['G28 X0 Y0'],
			'invert_z': False,
			'invert_x': False,
			'invert_y': False,
			'printer_model': {
				'id': None,
				'name': None
			},
			'temp_presets' : {
				'3e0fc9b398234f2f871310c1998aa000': {
					'name' : "PLA",
					'nozzle_temp' : 220,
					'bed_temp' : 40
				},
				'2cc9df599f3e4292b379913f4940c000': {
					'name' : "ABS",
					'nozzle_temp' : 230,
					'bed_temp' : 80
				},
			},
			'last_presets_used' : {}
		}
		config = None

		if not os.path.isfile(self._infoFile):
			factoryFile = "%s/printer-profile.factory" % configDir

			if os.path.isfile(factoryFile):
				with open(factoryFile, "r") as f:
					config = yaml.safe_load(f)

			if not config:
				config = {}

			if config:
				merge_dict(self.data, config)

			self.save()

		else:
			with open(self._infoFile, "r") as f:
				config = yaml.safe_load(f)
				# remove old array formats
				if 'temp_presets' in config and isinstance(config['temp_presets'], list) == True:
					del config['temp_presets']
				if 'last_presets_used'in config and isinstance(config['last_presets_used'], list) == True:
					del config['last_presets_used']

			if config:
				merge_dict(self.data, config)

		# check manufacturer definition update
		version = manufacturerPkgManager().version
		mfDefProfile = manufacturerPkgManager().printerProfile
		mfConfig = {}
		if version != self.data['last_definition_version']:
			self._logger.info("A New update for manufacturer package has been found: %s" % (version))

			mfDefVariant = manufacturerPkgManager().variant
			for k in mfDefProfile.keys():
				v = mfDefProfile[k]
				if v is not None:
					mfConfig[k] = v
					if k == "temp_presets":
						for mfPresetID in v.keys():
							p = mfConfig[k][mfPresetID]

							if self.data[k] is not None:
								dKey = self._checkPresetExisted(k, mfPresetID)
								if dKey:
									# if manufacturer updates its preset and user it's not allowed to edit => REPLACE
									if mfPresetID and mfDefVariant['temperature_presets_edit'] is False:
										mfConfig[k][dKey] = {
											"manufacturer_id": mfPresetID,
											"name": p['name'],
											"bed_temp": p['bed_temp'],
											"nozzle_temp": p['nozzle_temp'],
										}
										del mfConfig[k][mfPresetID]
									# if manfufacturer updates its preset and user it's allowed to edit => IGNORE UPDATE
									else:
										del mfConfig[k][mfPresetID]
								else:
									# Add new attribute object with correct format
									mfConfig[k][uuid.uuid4().hex] = {
										"manufacturer_id": mfPresetID,
										"name": p['name'],
										"bed_temp": p['bed_temp'],
										"nozzle_temp": p['nozzle_temp'],
									}
									del mfConfig[k][mfPresetID]
							else:
								mfConfig[k][uuid.uuid4().hex] = {
									"manufacturer_id": mfPresetID,
									"name": p['name'],
									"bed_temp": p['bed_temp'],
									"nozzle_temp": p['nozzle_temp'],
								}
								del mfConfig[k][mfPresetID]
			# update version number
			self.data['last_definition_version'] = version

		if mfConfig:
			if "temp_presets" in mfConfig.keys():
				self._removeDefaultTempPresets()
			merge_dict(self.data, mfConfig)
		self.save()

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
					elif k == 'printer_model':
						data = {
							"printerModel": changes[k]
						}
						astroprintCloud().updateBoxrouterData(data)
					self.data[k] = self._clean(k, changes[k])

					# Send astrobox event
					from octoprint.events import eventManager, Events

					eventManager().fire(Events.PRINTERPROFILE_CHANGE, { k: self.data[k]})

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

	def createTempPreset(self, name, nozzle_temp, bed_temp):
		id = uuid.uuid4().hex
		temp_update = { 'name' : name, 'nozzle_temp' : int(nozzle_temp), 'bed_temp' : int(bed_temp)}

		changes = self.data.copy()
		changes['temp_presets'][id] = temp_update
		self.set(changes)
		self.save()

		return id

	def _clean(self, field, value):
		if field in ['extruder_count', 'max_nozzle_temp', 'max_bed_temp']:
			return int(value)
		elif field == 'heated_bed':
			return bool(value)
		else:
			return value

	def _checkPresetExisted(self, key, presetID):
		for dkey in self.data[key].keys():
			if "manufacturer_id" in self.data[key][dkey]:
				if self.data[key][dkey]['manufacturer_id'] == presetID:
					return dkey

	def _removeDefaultTempPresets(self):
		if "3e0fc9b398234f2f871310c1998aa000" in self.data['temp_presets']:
			del self.data['temp_presets']['3e0fc9b398234f2f871310c1998aa000']
		if "2cc9df599f3e4292b379913f4940c000" in self.data['temp_presets']:
			del self.data['temp_presets']['2cc9df599f3e4292b379913f4940c000']
