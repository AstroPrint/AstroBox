# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import os
import yaml

from threading import Thread

from octoprint.settings import settings

from astroprint.plugin.printer_comms import PrinterCommsService

class Plugin(object):
	def __init__(self):
		self.logger = logging.getLogger('Plugin::%s' % self.__class__.__name__)
		self.initialize()

	def initialize(self):
		pass

class PluginManager(object):
	def __init__(self):
		self._logger = logging.getLogger("PluginManager")
		self._loaderWorker = None
		self._plugins = {}

	def loadPlugins(self):
		pluginsDir = settings().get(['folder', 'plugins'])

		if pluginsDir:
			self._loaderWorker = Thread(target=self._pluginLoaderWorker, args=(pluginsDir,))
			self._loaderWorker.start()
		else:
			self._logger.info("Plugins Folder is not configured")

	def _pluginLoaderWorker(self, pluginsDir):
		if os.path.isdir(pluginsDir):
			dirs = [ name for name in os.listdir(pluginsDir) if os.path.isdir(os.path.join(pluginsDir, name)) ]
			if dirs:
				import importlib
				import sys

				sys.path.insert(10, os.path.join(pluginsDir))

				for d in dirs:
					#We make sure that there's a plugin definition file
					configFile = os.path.join(pluginsDir, d, 'plugin.yaml')
					if os.path.exists(configFile):
						try:
							with open(configFile, "r") as f:
								config = yaml.safe_load(f)

						except Exception as e:
							self._logger.error("Failed to parse %s\n---\n%s\n---" % (configFile, e))
							continue

						if 'id' in config:
							pluginId = config['id']
							del config['id']

							if pluginId not in self._plugins:
								self._logger.info("Loading %s" % pluginId)
								self._plugins[pluginId] = config

								try:
									plugin = importlib.import_module(d)
									self._plugins[pluginId]['instance'] = plugin.__plugin_instance__

								except Exception as e:
									del self._plugins[pluginId]
									self._logger.error("Failed to initialize %s" % pluginId, exc_info= True)

							else:
								self._logger.error("Plugin [%s] has already been loaded" % pluginId)

						else:
							self._logger.error("No plugin ID found in %s" % configFile)
			else:
				self._logger.warn("Plugins Folder [%s] is empty" % pluginsDir)

		else:
			self._logger.error("Plugins Folder [%s] not found" % pluginsDir)
