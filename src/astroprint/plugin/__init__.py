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
		self._definition = None

		#Read it's definition file - plugin.yaml -
		pluginPath = os.path.dirname(sys.modules[self.__module__].__file__)
		definitionFile = os.path.join(pluginPath, 'plugin.yaml')
		if os.path.exists(definitionFile):
			try:
				with open(definitionFile, "r") as f:
					self._definition = yaml.safe_load(f)

			except Exception as e:
				raise e #Raise parse exception here

			if all(key in self._definition for key in ['id', 'name', 'services']):
				self.initialize()

			else:
				raise Exception("Invalid plugin definition found in %s" % definitionFile)

		else:
			raise Exception("No plugin definition file exists in %s" % pluginPath)


	@property
	def definition(self):
		return self._definition

	@property
	def pluginId(self):
		return self._definition['id']

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
		return {pId: self._plugins[pId] for pId in self._plugins if service in self._plugins[pId].definition['services']}

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
		#don't return hidden dirs
		return [ name for name in os.listdir(path) if name[0] != '.' and os.path.isdir(os.path.join(path, name)) ]

	def _loadPlugin(self, pluginsContainer, pluginDir, modulePrefix=''):
		try:
			plugin = importlib.import_module(modulePrefix + pluginDir)
			instance = plugin.__plugin_instance__
			pluginId = instance.pluginId

		except Exception as e:
			self._logger.error("Failed to initialize %s" % pluginDir, exc_info= True)
			return

		if pluginId not in self._plugins:
			self._logger.info("Loaded %s" % pluginId)
			self._plugins[pluginId] = instance

		else:
			self._logger.error("Plugin [%s] has already been loaded" % pluginId)


# Singleton management
_instance = None
def pluginManager():
	global _instance

	if not _instance:
		_instance = PluginManager()

	return _instance
