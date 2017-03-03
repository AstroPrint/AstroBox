# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import os
import yaml
import importlib
import sys

from threading import Thread, Event

from octoprint.settings import settings

from astroprint.plugin.printer_comms import PrinterCommsService

#
# Plugin Base Class
#

class Plugin(object):
	def __init__(self):
		self.logger = logging.getLogger('Plugin::%s' % self.__class__.__name__)
		self.initialize()

	# Optional functions for child classes

	#
	# Called when the plugin is first created and entered in the the list of available plugins.
	#
	def initialize(self):
		pass


#
# Plugin Manager
#

class PluginManager(object):
	def __init__(self):
		self._logger = logging.getLogger("PluginManager")
		self._loaderWorker = None
		self._plugins = {}
		self._pluginsLoaded = Event()

	def loadPlugins(self):
		userPluginsDir = settings().get(['folder', 'userPlugins'])

		if userPluginsDir:
			self._loaderWorker = Thread(target=self._pluginLoaderWorker, args=(userPluginsDir,))
			self._loaderWorker.start()
		else:
			self._logger.info("User Plugins Folder is not configured")

	def getPluginsByService(self, service):
		self._pluginsLoaded.wait()
		return {pId: self._plugins[pId] for pId in self._plugins if service in self._plugins[pId]['services']}

	def _pluginLoaderWorker(self, userPluginsDir):
		#System Plugins
		systemPluginsDir = os.path.realpath(os.path.join(os.path.dirname(__file__),'..','..','plugins'))
		dirs = self._getDirectories(systemPluginsDir)
		if dirs:
			for d in dirs:
				self._loadPlugin(systemPluginsDir, d, 'plugins.')

		else:
			self._logger.warn("System Plugins Folder [%s] is empty" % systemPluginsDir)


		# User Plugins
		if os.path.isdir(userPluginsDir):
			dirs = self._getDirectories(userPluginsDir)
			if dirs:
				sys.path.insert(10, os.path.join(userPluginsDir))

				for d in dirs:
					self._loadPlugin(userPluginsDir, d)

			else:
				self._logger.warn("User Plugins Folder [%s] is empty" % userPluginsDir)

		else:
			self._logger.error("User Plugins Folder [%s] not found" % userPluginsDir)

		self._pluginsLoaded.set() # Signal that plugin loading is done

	def _getDirectories(self, path):
		return [ name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name)) ]

	def _loadPlugin(self, pluginsContainer, pluginDir, modulePrefix=''):
		#We make sure that there's a plugin definition file
		configFile = os.path.join(os.path.join(pluginsContainer, pluginDir), 'plugin.yaml')
		if os.path.exists(configFile):
			try:
				with open(configFile, "r") as f:
					config = yaml.safe_load(f)

			except Exception as e:
				self._logger.error("Failed to parse %s\n---\n%s\n---" % (configFile, e))
				return

			if 'id' in config:
				pluginId = config['id']
				del config['id']

				if pluginId not in self._plugins:
					self._logger.info("Loading %s" % pluginId)
					self._plugins[pluginId] = config

					try:
						plugin = importlib.import_module(modulePrefix + pluginDir)
						self._plugins[pluginId]['instance'] = plugin.__plugin_instance__

					except Exception as e:
						del self._plugins[pluginId]
						self._logger.error("Failed to initialize %s" % pluginId, exc_info= True)

				else:
					self._logger.error("Plugin [%s] has already been loaded" % pluginId)

			else:
				self._logger.error("No plugin ID found in %s" % configFile)


# Singleton management
_instance = None
def pluginManager():
	global _instance

	if not _instance:
		_instance = PluginManager()

	return _instance
