# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def customCommandsManager():
	global _instance
	if _instance is None:
		_instance = CustomCommandsManager()
	return _instance

import yaml
import os
import logging

from octoprint.settings import settings

class CustomCommandsManager(object):
	def __init__(self):
		self._settings = settings()

		configDir = self._settings.getConfigFolder()

		self._commandsFile = "%s/custom-commands.yaml" % configDir
		self._logger = logging.getLogger(__name__)
		self.data = {}

		if self.fileExists():
			if self._commandsFile:
				with open(self._commandsFile, "r") as f:
					config = yaml.safe_load(f)

				def merge_dict(a,b):
					for key in b:
						if isinstance(b[key], dict):
							merge_dict(a[key], b[key])
						else:
							a[key] = b[key]

				if config:
					merge_dict(self.data, config)

	def fileExists(self):
		return os.path.isfile(self._commandsFile)
