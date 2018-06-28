# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import os
import yaml
import importlib
import sys
import zipfile
import shutil

from werkzeug.utils import secure_filename
from tempfile import gettempdir

from threading import Thread, Event

from octoprint.settings import settings
from octoprint.events import eventManager, Events as SystemEvent

from astroprint.plugin.providers.printer_comms import PrinterCommsService, PrinterState
from astroprint.printerprofile import printerProfileManager

PLUGIN_API_VERSION = 1
REQUIRED_PLUGIN_KEYS = ['id', 'name', 'providers', 'version', 'min_api_version']

#
# Plugin Base Class
#

class Plugin(object):
	def __init__(self):
		self.systemPlugin = False

		self._logger = logging.getLogger('Plugin::%s' % self.__class__.__name__)
		self._definition = None
		self._settings = settings()
		self._pluginEventListeners = {}
		self._profileManager = printerProfileManager()

		#Read it's definition file - plugin.yaml -
		pluginPath = os.path.dirname(sys.modules[self.__module__].__file__)
		definitionFile = os.path.join(pluginPath, 'plugin.yaml')
		if os.path.exists(definitionFile):
			try:
				with open(definitionFile, "r") as f:
					self._definition = yaml.safe_load(f)

			except Exception as e:
				raise e #Raise parse exception here

			if all(key in self._definition for key in REQUIRED_PLUGIN_KEYS):
				min_api_version = int(self._definition['min_api_version'])

				if PLUGIN_API_VERSION >= min_api_version:
					self.initialize()
				else:
					raise Exception("AstroBox API version [%d] is lower than minimum required by %s [%d]" % (PLUGIN_API_VERSION, self._definition['id'], min_api_version))

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

	@property
	def name(self):
		return self._definition['name']

	@property
	def version(self):
		return self._definition['version']

	@property
	def verified(self):
		return self._definition.get('verified', False)

	@property
	def providers(self):
		return self._definition['providers'] or []

	@property
	def pluginManager(self):
		return pluginManager()

	#
	# Services
	#

	@property
	def printer(self):
		return self.pluginManager.printer

	@property
	def files(self):
		return self.pluginManager.files

	@property
	def system(self):
		return self.pluginManager.system

	@property
	def network(self):
		return self.pluginManager.network

	@property
	def account(self):
		return self.pluginManager.account

	@property
	def auth(self):
		return self.pluginManager.auth

	@property
	def camera(self):
		return self.pluginManager.camera

	#
	# Directory path where the settings file (config.yaml) is stored
	#

	@property
	def settingsDir(self):
		return os.path.dirname(self._settings._configfile)

	#
	# Function to get a dependent plugin from the manager
	#
	def getPluginById(self, pluginId):
		return self.pluginManager.getPlugin(pluginId)

	#
	# Helper function for plugins to fire a system event
	#

	def fireSystemEvent(self, event, data=None):
		eventManager().fire(event, data)

	#
	# Function for plugins to fire a plugin specific events
	#

	def firePluginEvent(self, event, data=None):
		self.pluginManager._fireEvent('ON_PLUGIN_EVENT', [self.pluginId, event, data])

	#
	# Function for plugins to register for plugin events
	#
	# - callback receives 3 parametets: pluginId, event, data
	#

	def registerForPluginEvents(self, pluginId, event, callback):
		if self._pluginEventListeners:
			if pluginId in self._pluginEventListeners:
				if event in self._pluginEventListeners[pluginId]:
					self._pluginEventListeners[pluginId][event].append(callback)
				else:
					self._pluginEventListeners[pluginId][event] = [callback]

			else:
				self._pluginEventListeners[pluginId] = { event: [callback] }

		else:
			self._pluginEventListeners[pluginId] = { event: [callback] }
			self.pluginManager.addEventListener('ON_PLUGIN_EVENT', self._onPluginEvent)

	#
	# Function for plugins to register for plugin events
	#

	def unregisterForPluginEvents(self, pluginId= None, event= None, callback= None):
		if pluginId:
			if pluginId in self._pluginEventListeners:
				if event:
					if event in self._pluginEventListeners[pluginId]:
						if callback:
							if callback in self._pluginEventListeners[pluginId][event]:
								del self._pluginEventListeners[pluginId][event][self._pluginEventListeners[pluginId][event].index(callback)]

						else:
							del self._pluginEventListeners[pluginId][event]
				else:
					del self._pluginEventListeners[pluginId]

		else:
			self._pluginEventListeners = {}

		if not self._pluginEventListeners:
			self.pluginManager.removeEventListener('ON_PLUGIN_EVENT', self._onPluginEvent)

	# Optional functions for child classes

	#
	# Called when the plugin is first created and entered in the the list of available plugins.
	#
	def initialize(self):
		pass

	# Events: Implement if needed

	#
	# Called just before the plugin is to be removed
	#
	def onRemove(self):
		pass

	#
	# Called when the AstroBox service is shutting down
	#
	def onServiceShutdown(self):
		pass

	#~~~~~~~~~~~~~~~~~~~
	# Private functions
	#~~~~~~~~~~~~~~~~~~~

	def _onPluginEvent(self, pluginId, event, data=None):
		pluginListeners = self._pluginEventListeners.get(pluginId)
		if pluginListeners:
			eventListeners = pluginListeners.get(event)
			if eventListeners:
				for l in list(eventListeners):
					try:
						l(pluginId, event, data)
					except Exception as e:
						self._logger.error('Error processing event %s from %s: %s' % (event, pluginId, e), exc_info=True)

#
# Plugin Manager
#

class PluginManager(object):
	def __init__(self):
		self._logger = logging.getLogger("PluginManager")
		self._logger.info('Plugin Manager Initialized with Api Version: %d' % PLUGIN_API_VERSION)
		self._loaderWorker = None
		self._plugins = {}
		self._pluginsLoaded = Event()
		self._eventListeners = {}

		#service containers
		self._printerService = None
		self._fileService = None
		self._systemService = None
		self._accountService = None
		self._cameraService = None
		self._authService = None
		self._networkService = None

	@property
	def plugins(self):
		return self._plugins

	@property
	def printer(self):
		if self._printerService is None:
			from .services.printer import PrinterService

			self._printerService = PrinterService()

		return self._printerService

	@property
	def files(self):
		if self._fileService is None:
			from .services.files import FilesService

			self._fileService = FilesService()

		return self._fileService

	@property
	def system(self):
		if self._systemService is None:
			from .services.system import SystemService

			self._systemService = SystemService()

		return self._systemService


	@property
	def account(self):
		if self._accountService is None:
			from .services.account import AccountService

			self._accountService = AccountService()

		return self._accountService


	@property
	def auth(self):
		if self._authService is None:
			from .services.auth import AuthService

			self._authService = AuthService()

		return self._authService

	@property
	def camera(self):
		if self._cameraService is None:
			from .services.camera import CameraService

			self._cameraService = CameraService()

		return self._cameraService

	@property
	def network(self):
		if self._networkService is None:
			from .services.network import NetworkService

			self._networkService = NetworkService()

		return self._networkService

		@property
		def account(self):
			if self._accountService is None:
				from .services.account import AccountService

				self._accountService = AcoountService()

			return self._accountService

		@property
		def network(self):
			if self._networkService is None:
				from .services.network import NetworkService

				self._networkService = NetworkService()

			return self._networkService
	#
	# Events are:
	#
	# - ON_PLUGIN_REMOVED: Called when a plugin is removed
	#			plugin: The plugin that was removed.
	#
	# - ON_ALL_PLUGINS_LOADED: Called when all plugins have been loaded
	#			No parameters.
	#
	#	- ON_PLUGIN_EVENT: Called when a plugin has fired an arbitraty event
	#
	def addEventListener(self, event, listener):
		if event in self._eventListeners:
			self._eventListeners[event].append(listener)
		else:
			self._eventListeners[event] = [listener]

	def removeEventListener(self, event, listener=None):
		if event in self._eventListeners:
			if listener:
				if listener in self._eventListeners[event]:
					del self._eventListeners[event][self._eventListeners[event].index(listener)]

			else:
				del self._eventListeners[event]

	def _fireEvent(self, event, params=[]):
		listeners = self._eventListeners.get(event)
		if listeners:
			for e in list(listeners):
				try:
					e(*params)
				except Exception as e:
					self._logger.error('Error in event Listener for [%s]' % event, exc_info=True)

	def checkFile(self, file):
		filename = file.filename

		if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in ['zip']):
			return {'error':'invalid_file'}

		savedFile = os.path.join(gettempdir(), secure_filename(file.filename))
		try:
			file.save(savedFile)
			zip_ref = zipfile.ZipFile(savedFile, 'r')
			pluginInfo = zip_ref.open('plugin.yaml', 'r')
			definition = yaml.safe_load(pluginInfo)

		except KeyError:
			zip_ref.close()
			os.unlink(savedFile)
			return {'error':'invalid_plugin_file'}

		except:
			zip_ref.close()
			os.unlink(savedFile)
			self._logger.error('Error checking uploaded Zip file', exc_info=True)
			return {'error':'error_checking_file'}

		zip_ref.close()

		if not all(key in definition for key in REQUIRED_PLUGIN_KEYS):
			os.unlink(savedFile)
			return {'error':'invalid_plugin_definition'}

		#Check if the min_api_version is valid
		min_api_version = int(definition['min_api_version'])
		if PLUGIN_API_VERSION < min_api_version:
			os.unlink(savedFile)
			return {'error':'incompatible_plugin', 'api_version': min_api_version}

		plugin = self.getPlugin(definition['id'])
		if plugin:
			os.unlink(savedFile)
			return {'error':'already_installed'}

		response = {
			'tmp_file': savedFile,
			'definition': definition
		}

		return response

	def installFile(self, filename):
		if os.path.isfile(filename):
			userPluginsDir = settings().getBaseFolder('userPlugins')

			#extract the contents of the plugin in it's directory
			zip_ref = zipfile.ZipFile(filename, 'r')
			pluginInfo = zip_ref.open('plugin.yaml', 'r')
			definition = yaml.safe_load(pluginInfo)

			pluginId = definition.get('id')
			if pluginId:
				pluginDir = os.path.join(userPluginsDir, pluginId.replace('.','_'))
				zip_ref.extractall(pluginDir)
				zip_ref.close()
				return self._loadPlugin(pluginId.replace('.','_')) is not None

			zip_ref.close()

		return False

	def removePlugin(self, pId):
		plugin = self.getPlugin(pId)

		if plugin:
			#Tell the plugin
			plugin.onRemove()

			#remove from the internal structure
			del self._plugins[pId]

			#remove the files from its directory
			userPluginsDir = settings().getBaseFolder('userPlugins')
			shutil.rmtree( os.path.join(userPluginsDir, pId.replace('.','_')) )

			#Tell all the listeners to the manager's [ON_PLUGIN_REMOVED] event
			self._fireEvent('ON_PLUGIN_REMOVED', [plugin])

			self._logger.info("Removed --> %s, version: %s" % (plugin.pluginId, plugin.version))

			return {'removed': pId, 'providers': plugin.providers}

		else:
			return {'error': 'not_found'}

	def loadPlugins(self):
		userPluginsDir = settings().getBaseFolder('userPlugins')

		sys.path.insert(10, userPluginsDir)

		if userPluginsDir:
			self._loaderWorker = Thread(target=self._pluginLoaderWorker, args=(userPluginsDir,))
			self._loaderWorker.start()
		else:
			self._logger.info("User Plugins Folder is not configured")

	def shutdown(self):
		for pId, p in self._plugins.iteritems():
			try:
				p.onServiceShutdown()

			except:
				self._logger.warn("Error shutting down plugin [%s]" % p.name, exc_info= True)

	def getPluginsByProvider(self, provider):
		self._pluginsLoaded.wait()
		return {pId: p for pId, p in self._plugins.iteritems() if provider in p.providers}

	def getPlugin(self, pluginId):
		self._pluginsLoaded.wait()
		return self._plugins.get(pluginId)

	def _pluginLoaderWorker(self, userPluginsDir):
		#System Plugins
		systemPluginsDir = os.path.realpath(os.path.join(os.path.dirname(__file__),'..','..','plugins'))
		dirs = self._getDirectories(systemPluginsDir)
		if dirs:
			for d in dirs:
				p = self._loadPlugin(d, 'plugins.')
				if p is not None:
					p.systemPlugin = True

		else:
			self._logger.warn("System Plugins Folder [%s] is empty" % systemPluginsDir)

		# User Plugins
		if os.path.isdir(userPluginsDir):
			dirs = self._getDirectories(userPluginsDir)
			if dirs:
				for d in dirs:
					self._loadPlugin(d)

			else:
				self._logger.warn("User Plugins Folder [%s] is empty" % userPluginsDir)

		else:
			self._logger.error("User Plugins Folder [%s] not found" % userPluginsDir)

		self._pluginsLoaded.set() # Signal that plugin loading is done
		self._fireEvent('ON_ALL_PLUGINS_LOADED')

	def _getDirectories(self, path):
		#don't return hidden dirs
		return [ name for name in os.listdir(path) if name[0] != '.' and os.path.isdir(os.path.join(path, name)) ]

	def _loadPlugin(self, pluginDir, modulePrefix=''):
		try:
			plugin = importlib.import_module(modulePrefix + pluginDir)
			instance = plugin.__plugin_instance__
			pluginId = instance.pluginId

		except ImportError:
			self._logger.warn("Directory [ %s ] doesn't contain a plugin" % pluginDir, exc_info= True)
			return

		except Exception as e:
			self._logger.error("Failed to initialize %s" % pluginDir, exc_info= True)
			return

		self._logger.info("Loaded --> %s, version: %s" % (pluginId, instance.version))
		self._plugins[pluginId] = instance
		return instance


# Singleton management
_instance = None
def pluginManager():
	global _instance

	if not _instance:
		_instance = PluginManager()

	return _instance
