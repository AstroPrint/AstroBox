# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import sys
import os
import yaml
import logging
import re
import shutil

APPNAME="AstroBox"

instance = None

def settings(init=False, configfile=None, basedir=None):
	global instance
	if instance is None:
		if init:
			instance = Settings(configfile, basedir)
		else:
			raise ValueError("Settings not initialized yet")
	return instance

default_settings = {
	"serial": {
		"port": None,
		"baudrate": None,
		"autoconnect": True,
		"log": False,
		"dsrdtrFlowControl": False,
		"rtsctsFlowControl": False,
		"swFlowControl": True,
		"timeout": {
			"detection": 0.5,
			"connection": 2.0,
			"communication": 10.0,
			"first_contact": 20.0, #Should be used a timeout to wait for the printer to responde on first connect attempt
			"temperature": 5,
			"sdStatus": 1
		},
		"additionalPorts": []
	},
	"server": {
		"host": "0.0.0.0",
		"port": 5000,
		"firstRun": True,
		"baseUrl": "",
		"scheme": "",
		"maxUploadSize": 200, #Size in MB for the max allowed file size
	},
	"camera": {
		"manager": "gstreamer",
		"encoding": "h264",
		"size": "640x480",
		"framerate": "15/1",
		"format": "x-raw", #This is used by mpjeg Manager
		"pixelformat": "YUYV", #This is used by GStreamer Manager
		"source": "USB",
		"debug-level": 0,
		"graphic-debug": False,
		"video-rotation": 0,
		"inactivitySecs": 90.0 # After 1.5 minutes of inactivity the camera shuts off
	},
	"gcodeViewer": {
		"enabled": True,
		"mobileSizeThreshold": 2 * 1024 * 1024, # 2MB
		"sizeThreshold": 20 * 1024 * 1024, # 20MB
	},
	"feature": {
		"temperatureGraph": True,
		"waitForStartOnConnect": False,
		"alwaysSendChecksum": False,
		"sdSupport": True,
		"sdAlwaysAvailable": False,
		"swallowOkAfterResend": True,
		"repetierTargetTemp": False
	},
	"folder": {
		"uploads": None,
		"timelapse": None,
		"timelapse_tmp": None,
		"logs": None,
		"virtualSd": None,
		"userPlugins": None,
		"tasks": None,
		"manufacturerPkg": None
	},
	"temperature": {
		"profiles":
			[
				{"name": "ABS", "extruder" : 210, "bed" : 100 },
				{"name": "PLA", "extruder" : 180, "bed" : 60 }
			]
	},
	"printerParameters": {
		"movementSpeed": {
			"x": 6000,
			"y": 6000,
			"z": 700,
			"e": 100
		},
		"pauseTriggers": [],
		"invertAxes": [],
		"numExtruders": 1,
		"extruderOffsets": [
			{"x": 0.0, "y": 0.0}
		],
		"bedDimensions": {
			"x": 200.0, "y": 200.0, "r": 100
		}
	},
	"appearance": {
		"name": "",
		"color": "default"
	},
	"controls": [],
	"system": {
		"actions": []
	},
	"accessControl": {
		"enabled": True,
		"userManager": "astroprint.users.FilebasedUserManager",
		"userfile": None,
		"autologinLocal": False,
		"localNetworks": ["127.0.0.0/8"],
		"autologinAs": None
	},
	"cura": {
		"enabled": False,
		"path": "/default/path/to/cura",
		"config": "/default/path/to/your/cura/config.ini"
	},
	"cloudSlicer": {
		"apiHost": "https://api.astroprint.com",
		"loggedUser": None,
		"boxrouter": "wss://boxrouter.astroprint.com"
	},
	"events": {
		"enabled": False,
		"subscriptions": []
	},
	"api": {
		"enabled": True,
		"key": None,
		"regenerate": True,
		"allowCrossOrigin": True
	},
	"terminalFilters": [
		{ "name": "Suppress M105 requests/responses", "regex": "(Send: M105)|(Recv: ok T\d*:)" },
		{ "name": "Suppress M27 requests/responses", "regex": "(Send: M27)|(Recv: SD printing byte)" }
	],
	"devel": {
		"stylesheet": "css",
		"virtualPrinter": {
			"enabled": False,
			"okAfterResend": False,
			"forceChecksum": False,
			"okWithLinenumber": False,
			"numExtruders": 1,
			"includeCurrentToolInTemps": True,
			"hasBed": True,
			"repetierStyleTargetTemperature": False,
			"extendedSdFileList": False
		}
	},
	"wifi": {
		"hotspotDevice": None,
		"hotspotOnlyOffline": True,
	},
	"network": {
		"manager": "debianNetworkManager",
		"interface": 'wlan0'
	},
	"software": {
		"infoDir": None,
		"variantFile": None,
		"useUnreleased": False,
		"lastCheck": None,
		"channel": 20 #production
	},
	"printerSelected": None,
	"materialSelected": None,
	"qualitySelected": None,
	"customQualitySelected": None
}

valid_boolean_trues = [True, "true", "yes", "y", "1"]

class Settings(object):

	def __init__(self, configfile=None, basedir=None):
		self._logger = logging.getLogger(__name__)

		self.settings_dir = None

		self._config = None
		self._dirty = False

		if configfile is not None:
			self._configfile = configfile

		else:
			if basedir:
				settings_dir = basedir
			else:
				settings_dir = os.path.realpath(os.path.dirname(__file__)+'/../../local')

			self._configfile = os.path.join(settings_dir, "config.yaml")

		self._init_settings_dir(basedir)

		self._factoryConfigFile = os.path.join(os.path.dirname(self._configfile), "config.factory")

		self.load()

	def _init_settings_dir(self, basedir):
		if basedir is not None:
			self.settings_dir = basedir
		else:
			self.settings_dir = self.getConfigFolder()

	def _getDefaultFolder(self, type):
		folder = default_settings["folder"][type]
		if folder is None:
			folder = os.path.join(self.settings_dir, type.replace("_", os.path.sep))
		return folder

	#~~ load and save

	def load(self):
		if os.path.exists(self._factoryConfigFile) and not os.path.exists(self._configfile):
			shutil.copy(self._factoryConfigFile, self._configfile)

		if os.path.exists(self._configfile) and os.path.isfile(self._configfile):
			with open(self._configfile, "r") as f:
				self._config = yaml.safe_load(f)

		# chamged from else to handle cases where the file exists, but is empty / 0 bytes
		if not self._config:
			self._config = {}

	def save(self, force=False):
		if not self._dirty and not force:
			return

		with open(self._configfile, "wb") as configFile:
			yaml.safe_dump(self._config, configFile, default_flow_style=False, indent="    ", allow_unicode=True)
			self._dirty = False
		self.load()

	#~~ getter

	def get(self, path, asdict=False):
		if len(path) == 0:
			return None

		config = self._config
		defaults = default_settings

		while len(path) > 1:
			key = path.pop(0)
			if key in config.keys() and key in defaults.keys():
				config = config[key]
				defaults = defaults[key]
			elif key in defaults.keys():
				config = {}
				defaults = defaults[key]
			else:
				return None

		k = path.pop(0)
		if not isinstance(k, (list, tuple)):
			keys = [k]
		else:
			keys = k

		if asdict:
			results = {}
		else:
			results = []
		for key in keys:
			if key in config.keys():
				value = config[key]
			elif key in defaults:
				value = defaults[key]
			else:
				value = None

			if asdict:
				results[key] = value
			else:
				results.append(value)

		if not isinstance(k, (list, tuple)):
			if asdict:
				return results.values().pop()
			else:
				return results.pop()
		else:
			return results

	def getInt(self, path):
		value = self.get(path)
		if value is None:
			return None

		try:
			return int(value)
		except ValueError:
			self._logger.warn("Could not convert %r to a valid integer when getting option %r" % (value, path))
			return None

	def getString(self, path):
		value = self.get(path)
		if value is None:
			return None

		try:
			return str(value)
		except ValueError:
			self._logger.warn("Could not convert %r to a valid string when getting option %r" % (value, path))
			return None

	def getFloat(self, path):
		value = self.get(path)
		if value is None:
			return None

		try:
			return float(value)
		except ValueError:
			self._logger.warn("Could not convert %r to a valid integer when getting option %r" % (value, path))
			return None

	def getBoolean(self, path):
		value = self.get(path)
		if value is None:
			return None
		if isinstance(value, bool):
			return value
		return value.lower() in valid_boolean_trues

	def getBaseFolder(self, type):
		if type not in default_settings["folder"].keys():
			return None

		folder = self.get(["folder", type])
		if folder is None:
			folder = self._getDefaultFolder(type)

		if not os.path.isdir(folder):
			os.makedirs(folder)

		return folder

	def getConfigFolder(self):
		return os.path.dirname(self._configfile)

	def getFeedbackControls(self):
		feedbackControls = []
		for control in self.get(["controls"]):
			feedbackControls.extend(self._getFeedbackControls(control))
		return feedbackControls

	def _getFeedbackControls(self, control=None):
		if control["type"] == "feedback_command" or control["type"] == "feedback":
			pattern = control["regex"]
			try:
				matcher = re.compile(pattern)
				return [(control["name"], matcher, control["template"])]
			except:
				# invalid regex or something like this, we'll just skip this entry
				pass
		elif control["type"] == "section":
			result = []
			for c in control["children"]:
				result.extend(self._getFeedbackControls(c))
			return result
		else:
			return []

	def getPauseTriggers(self):
		triggers = {
			"enable": [],
			"disable": [],
			"toggle": []
		}
		for trigger in self.get(["printerParameters", "pauseTriggers"]):
			try:
				regex = trigger["regex"]
				type = trigger["type"]
				if type in triggers.keys():
					# make sure regex is valid
					re.compile(regex)
					# add to type list
					triggers[type].append(regex)
			except:
				# invalid regex or something like this, we'll just skip this entry
				pass

		result = {}
		for type in triggers.keys():
			if len(triggers[type]) > 0:
				result[type] = re.compile("|".join(map(lambda x: "(%s)" % x, triggers[type])))
		return result

	#~~ setter

	def set(self, path, value, force=False):
		if len(path) == 0:
			return

		config = self._config
		defaults = default_settings

		while len(path) > 1:
			key = path.pop(0)
			if key in config.keys() and key in defaults.keys():
				config = config[key]
				defaults = defaults[key]
			elif key in defaults.keys():
				config[key] = {}
				config = config[key]
				defaults = defaults[key]
			else:
				return

		key = path.pop(0)
		if not force and key in defaults.keys() and key in config.keys() and defaults[key] == value:
			del config[key]
			self._dirty = True
		elif force or (not key in config.keys() and defaults[key] != value) or (key in config.keys() and config[key] != value):
			if value is None:
				if key in config:
					del config[key]
			else:
				config[key] = value
			self._dirty = True

	def setInt(self, path, value, force=False):
		if value is None:
			self.set(path, None, force)
			return

		try:
			intValue = int(value)
		except ValueError:
			self._logger.warn("Could not convert %r to a valid integer when setting option %r" % (value, path))
			return

		self.set(path, intValue, force)

	def setFloat(self, path, value, force=False):
		if value is None:
			self.set(path, None, force)
			return

		try:
			floatValue = float(value)
		except ValueError:
			self._logger.warn("Could not convert %r to a valid integer when setting option %r" % (value, path))
			return

		self.set(path, floatValue, force)

	def setBoolean(self, path, value, force=False):
		if value is None or isinstance(value, bool):
			self.set(path, value, force)
		elif value.lower() in valid_boolean_trues:
			self.set(path, True, force)
		else:
			self.set(path, False, force)

	def setBaseFolder(self, type, path, force=False):
		if type not in default_settings["folder"].keys():
			return None

		currentPath = self.getBaseFolder(type)
		defaultPath = self._getDefaultFolder(type)
		if (path is None or path == defaultPath) and "folder" in self._config.keys() and type in self._config["folder"].keys():
			del self._config["folder"][type]
			if not self._config["folder"]:
				del self._config["folder"]
			self._dirty = True
		elif (path != currentPath and path != defaultPath) or force:
			if not "folder" in self._config.keys():
				self._config["folder"] = {}
			self._config["folder"][type] = path
			self._dirty = True
