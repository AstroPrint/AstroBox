# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com> based on work done by Gina Häußge"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import uuid
import json
import threading
import os
import time
import logging
import logging.config
import tornado.wsgi

from ext.sockjs.tornado import SockJSRouter
from flask import Flask, render_template, send_from_directory, make_response, Response, request, abort
from flask_login import LoginManager, current_user, logout_user
from flask_principal import Principal, Permission, RoleNeed, identity_loaded, UserNeed
from flask_compress import Compress
from flask_assets import Environment
from watchdog.observers import Observer
from sys import platform


SUCCESS = {}
NO_CONTENT = ("", 204)
OK = ("", 200)

debug = False

app = Flask("octoprint", template_folder="../astroprint/templates", static_folder='../astroprint/static')
app.config.from_object('astroprint.settings')

app_config_file = os.path.join(os.path.realpath(os.path.dirname(__file__)+'/../../../local'), "application.cfg")
if os.path.isfile(app_config_file):
	app.config.from_pyfile(app_config_file, silent=True)
elif platform == "linux2" and os.path.isfile('/etc/astrobox/application.cfg'):
	app.config.from_pyfile('/etc/astrobox/application.cfg', silent=True)

assets = Environment(app)
Compress(app)

userManager = None
eventManager = None
loginManager = None
softwareManager = None
discoveryManager = None

principals = Principal(app)
admin_permission = Permission(RoleNeed("admin"))
user_permission = Permission(RoleNeed("user"))

# only import the octoprint stuff down here, as it might depend on things defined above to be initialized already
from octoprint.server.util import LargeResponseHandler, ReverseProxied, restricted_access, PrinterStateConnection, admin_validator, UrlForwardHandler, user_validator
from astroprint.printer.manager import printerManager
from octoprint.settings import settings
import octoprint.util as util
import octoprint.events as events
#import octoprint.timelapse

import astroprint.users as users

from astroprint.software import softwareManager as swManager
from astroprint.boxrouter import boxrouterManager
from astroprint.network.manager import networkManager
from astroprint.camera import cameraManager
from astroprint.printfiles.downloadmanager import downloadManager
from astroprint.webrtc import webRtcManager
from astroprint.printerprofile import printerProfileManager
from astroprint.additionaltasks import additionalTasksManager
from astroprint.maintenancemenu import maintenanceMenuManager
from astroprint.discovery import DiscoveryManager
from astroprint.plugin import pluginManager
from astroprint.externaldrive import externalDriveManager
from astroprint.manufacturerpkg import manufacturerPkgManager

UI_API_KEY = None
VERSION = None

@app.route('/astrobox/identify', methods=['GET'])
def box_identify():
	nm = networkManager()
	s = settings()

	return Response(json.dumps({
		'id': boxrouterManager().boxId,
		'name': nm.getHostname(),
		'version': VERSION,
		'firstRun': s.getBoolean(["server", "firstRun"]),
		'online': nm.isOnline()
	}),
	headers= {
		'Access-Control-Allow-Origin': '*'
	} if s.getBoolean(['api', 'allowCrossOrigin']) else None)

@app.route("/")
def index():
	s = settings()
	loggedUsername = s.get(["cloudSlicer", "loggedUser"])
	publicKey = None

	if loggedUsername:
		user = userManager.findUser(loggedUsername)
		if user:
			publicKey = user.publicKey

	if (s.getBoolean(["server", "firstRun"])):
		swm = swManager()

		# we need to get the user to sign into their AstroPrint account
		return render_template(
			"setup.jinja2",
			debug= debug,
			uiApiKey= UI_API_KEY,
			version= VERSION,
			commit= swm.commit,
			astroboxName= networkManager().getHostname(),
			checkSoftware= swm.shouldCheckForNew,
			settings= s,
			wsToken= create_ws_token(publicKey),
			mfDefinition= manufacturerPkgManager()
		)

	elif softwareManager.status != 'idle' or softwareManager.forceUpdateInfo:
		return render_template(
			"updating.jinja2",
			uiApiKey= UI_API_KEY,
			forceUpdateInfo=  softwareManager.forceUpdateInfo,
			releases= softwareManager.updatingReleases or [softwareManager.forceUpdateInfo['id']],
			lastCompletionPercent= softwareManager.lastCompletionPercent,
			lastMessage= softwareManager.lastMessage,
			astroboxName= networkManager().getHostname(),
			wsToken= create_ws_token(publicKey),
			status= softwareManager.status,
			mfDefinition= manufacturerPkgManager()
		)

	elif loggedUsername and (current_user is None or not current_user.is_authenticated or current_user.get_id() != loggedUsername):
		if current_user.is_authenticated:
			logout_user()
		return render_template(
			"locked.jinja2",
			username= loggedUsername,
			uiApiKey= UI_API_KEY,
			astroboxName= networkManager().getHostname(),
			mfDefinition= manufacturerPkgManager()
		)

	else:
		pm = printerManager()
		nm = networkManager()
		swm = swManager()
		cm = cameraManager()
		mmm = maintenanceMenuManager()

		paused = pm.isPaused()
		printing = pm.isPrinting()
		online = nm.isOnline()

		return render_template(
			"app.jinja2",
			user_email= loggedUsername,
			show_bad_shutdown= swm.wasBadShutdown and not swm.badShutdownShown,
			version= VERSION,
			commit= swm.commit,
			printing= printing,
			paused= paused,
			online= online,
			print_capture= cm.timelapseInfo if printing or paused else None,
			printer_profile= printerProfileManager().data,
			uiApiKey= UI_API_KEY,
			astroboxName= nm.getHostname(),
			checkSoftware= swm.shouldCheckForNew,
			serialLogActive= s.getBoolean(['serial', 'log']),
			additionalTasks= True,
			maintenanceMenu= True,
			cameraManager= cm.name,
			wsToken= create_ws_token(publicKey),
			mfDefinition= manufacturerPkgManager()
		)

@app.route("/discovery.xml")
def discoveryXml():
	response = make_response( discoveryManager.getDiscoveryXmlContents() )
	response.headers['Content-Type'] = 'application/xml'
	return response

@app.route("/robots.txt")
def robotsTxt():
	return send_from_directory(app.static_folder, "robots.txt")

@app.route("/favicon.ico")
def favion():
	return send_from_directory(app.static_folder, "favicon.ico")

@app.route("/apple-touch-icon.png")
def apple_icon():
	return send_from_directory(app.static_folder, "apple-touch-icon.png")

@app.route('/img/<path:path>')
def static_proxy_images(path):
	return app.send_static_file(os.path.join('img', path))

@app.route('/font/<path:path>')
def static_proxy_fonts(path):
	return app.send_static_file(os.path.join('font', path))

@app.route('/camera/snapshot', methods=["GET"])
@restricted_access
def camera_snapshot():
	cameraMgr = cameraManager()
	pic_buf = cameraMgr.get_pic(text=request.args.get('text'))
	if pic_buf:
		return Response(pic_buf, mimetype='image/jpeg', headers={"Access-Control-Allow-Origin": "*"})
	else:
		return 'Camera not ready', 404


@app.route("/status", methods=["GET"])
@restricted_access
def getStatus():
	printer = printerManager()
	cm = cameraManager()
	softwareManager = swManager()

	fileName = None

	if printer.isPrinting():
		currentJob = printer.getCurrentJob()
		fileName = currentJob["file"]["name"]

	return Response(
		json.dumps({
			'id': boxrouterManager().boxId,
			'name': networkManager().getHostname(),
			'printing': printer.isPrinting(),
			'fileName': fileName,
			'printerModel': None,
			'material': None,
			'operational': printer.isOperational(),
			'paused': printer.isPaused(),
			'camera': cm.isCameraConnected(),
			#'printCapture': cm.timelapseInfo,
			'remotePrint': True,
			'capabilities': softwareManager.capabilities() + cm.capabilities
		}),
		mimetype= 'application/json',
		headers= {
			'Access-Control-Allow-Origin': '*'
		} if settings().getBoolean(['api', 'allowCrossOrigin']) else None
	)

@app.route("/wsToken", methods=['GET'])
def getWsToken():
	publicKey = None
	userLogged = settings().get(["cloudSlicer", "loggedUser"])

	if userLogged:
		if current_user.is_anonymous or current_user.get_name() != userLogged:
			abort(401, "Unauthorized Access")

		user = userManager.findUser(userLogged)
		if user:
			publicKey = user.publicKey
		else:
			abort(403, 'Invalid Logged User')

	return Response(
		json.dumps({
		'ws_token': create_ws_token(publicKey)
		}),
		headers= {
			'Access-Control-Allow-Origin': '*'
		} if settings().getBoolean(['api', 'allowCrossOrigin']) else None
	)

@app.route("/accessKeys", methods=["POST"])
def getAccessKeys():
	from astroprint.cloud import astroprintCloud

	publicKey = None
	email = request.values.get('email', None)
	accessKey = request.values.get('accessKey', None)

	userLogged = settings().get(["cloudSlicer", "loggedUser"])
	####
	# - nobody logged: None
	# - any log: email

	if email and accessKey:#somebody is logged in the remote client
		if userLogged:#Somebody logged in Astrobox
			if userLogged == email:#I am the user logged
				online = networkManager().isOnline()

				if online:
					publicKey = astroprintCloud().get_public_key(email, accessKey)

					if not publicKey:
						abort(403)

				else:
					user = userManager.findUser(email)
					if user.get_private_key() != accessKey:
						abort(403)

			else:#I am NOT the logged user
				abort(403)

	else:#nodody is logged in the remote client
		if userLogged:
			abort(401)

	return Response(
		json.dumps({
			'api_key': UI_API_KEY,
			'ws_token': create_ws_token(publicKey)
		}),
		mimetype= 'application/json',
		headers= {
			'Access-Control-Allow-Origin': '*'
		} if settings().getBoolean(['api', 'allowCrossOrigin']) else None
	)


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
	user = load_user(identity.id)
	if user is None:
		return

	identity.provides.add(UserNeed(user.get_name()))
	if user.is_user():
		identity.provides.add(RoleNeed("user"))
	if user.is_admin():
		identity.provides.add(RoleNeed("admin"))

def load_user(id):
	if userManager is not None:
		return userManager.findUser(id)
	return users.DummyUser()

def create_ws_token(public_key= None):
	from itsdangerous import URLSafeTimedSerializer

	s = URLSafeTimedSerializer(UI_API_KEY)
	return s.dumps({ 'public_key': public_key })

def read_ws_token(token):
	if not token:
		return None

	from itsdangerous import URLSafeTimedSerializer, BadSignature

	s = URLSafeTimedSerializer(UI_API_KEY)

	try:
		return s.loads(token, max_age= 10)
	except BadSignature as e:
		return None

#~~ startup code


class Server():
	def __init__(self, configfile=None, basedir=None, host="0.0.0.0", port=5000, debug=False, allowRoot=False, logConf=None):
		self._configfile = configfile
		self._basedir = basedir
		self._host = host
		self._port = port
		self._debug = debug
		self._allowRoot = allowRoot
		self._logConf = logConf
		self._ioLoop = None

	def stop(self):
		if self._ioLoop:
			self._ioLoop.stop()
			self._ioLoop = None

	def run(self):
		if not self._allowRoot:
			self._checkForRoot()

		global userManager
		global eventManager
		global loginManager
		global debug
		global softwareManager
		global discoveryManager
		global VERSION
		global UI_API_KEY

		from tornado.wsgi import WSGIContainer
		from tornado.httpserver import HTTPServer
		from tornado.ioloop import IOLoop
		from tornado.web import Application, FallbackHandler

		from astroprint.printfiles.watchdogs import UploadCleanupWatchdogHandler

		debug = self._debug

		# first initialize the settings singleton and make sure it uses given configfile and basedir if available
		self._initSettings(self._configfile, self._basedir)
		s = settings()

		if not s.getBoolean(['api', 'regenerate']) and s.getString(['api', 'key']):
			UI_API_KEY = s.getString(['api', 'key'])
		else:
			UI_API_KEY = ''.join('%02X' % ord(z) for z in uuid.uuid4().bytes)

		# then initialize logging
		self._initLogging(self._debug, self._logConf)
		logger = logging.getLogger(__name__)

		if s.getBoolean(["accessControl", "enabled"]):
			userManagerName = s.get(["accessControl", "userManager"])
			try:
				clazz = util.getClass(userManagerName)
				userManager = clazz()
			except AttributeError, e:
				logger.exception("Could not instantiate user manager %s, will run with accessControl disabled!" % userManagerName)

		softwareManager = swManager()
		VERSION = softwareManager.versionString

		logger.info("Starting AstroBox (%s) - Commit (%s)" % (VERSION, softwareManager.commit))

		from astroprint.migration import migrateSettings
		migrateSettings()

		manufacturerPkgManager()
		ppm = printerProfileManager()
		pluginManager().loadPlugins()

		eventManager = events.eventManager()
		printer = printerManager(ppm.data['driver'])

		#Start some of the managers here to make sure there are no thread collisions
		from astroprint.network.manager import networkManager
		from astroprint.boxrouter import boxrouterManager

		networkManager()
		boxrouterManager()

		# configure timelapse
		#octoprint.timelapse.configureTimelapse()

		app.wsgi_app = ReverseProxied(app.wsgi_app)

		app.secret_key = boxrouterManager().boxId
		loginManager = LoginManager()
		loginManager.session_protection = "strong"
		loginManager.user_callback = load_user
		if userManager is None:
			loginManager.anonymous_user = users.DummyUser
			principals.identity_loaders.appendleft(users.dummy_identity_loader)
		loginManager.init_app(app)

		# setup command triggers
		events.CommandTrigger(printer)
		if self._debug:
			events.DebugEventListener()

		if networkManager().isOnline():
			softwareManager.checkForcedUpdate()

		if self._host is None:
			self._host = s.get(["server", "host"])
		if self._port is None:
			self._port = s.getInt(["server", "port"])

		app.debug = self._debug

		from octoprint.server.api import api

		app.register_blueprint(api, url_prefix="/api")

		boxrouterManager() # Makes sure the singleton is created here. It doesn't need to be stored
		self._router = SockJSRouter(self._createSocketConnection, "/sockjs")

		discoveryManager = DiscoveryManager()

		externalDriveManager()

		def access_validation_factory(validator):
			"""
			Creates an access validation wrapper using the supplied validator.

			:param validator: the access validator to use inside the validation wrapper
			:return: an access validation wrapper taking a request as parameter and performing the request validation
			"""
			def f(request):
				"""
				Creates a custom wsgi and Flask request context in order to be able to process user information
				stored in the current session.

				:param request: The Tornado request for which to create the environment and context
				"""
				wsgi_environ = tornado.wsgi.WSGIContainer.environ(request)
				with app.request_context(wsgi_environ):
					app.session_interface.open_session(app, request)
					loginManager.reload_user()
					validator(request)
			return f

		self._tornado_app = Application(self._router.urls + [
			#(r"/downloads/timelapse/([^/]*\.mpg)", LargeResponseHandler, {"path": s.getBaseFolder("timelapse"), "as_attachment": True}),
			(r"/downloads/files/local/([^/]*\.(gco|gcode))", LargeResponseHandler, {"path": s.getBaseFolder("uploads"), "as_attachment": True}),
			(r"/downloads/logs/([^/]*)", LargeResponseHandler, {"path": s.getBaseFolder("logs"), "as_attachment": True, "access_validation": access_validation_factory(admin_validator)}),
			#(r"/downloads/camera/current", UrlForwardHandler, {"url": s.get(["webcam", "snapshot"]), "as_attachment": True, "access_validation": access_validation_factory(user_validator)}),
			(r".*", FallbackHandler, {"fallback": WSGIContainer(app.wsgi_app)})
		])
		self._server = HTTPServer(self._tornado_app, max_buffer_size=1048576 * s.getInt(['server', 'maxUploadSize']))
		self._server.listen(self._port, address=self._host)

		logger.info("Listening on http://%s:%d" % (self._host, self._port))

		eventManager.fire(events.Events.STARTUP)
		if s.getBoolean(["serial", "autoconnect"]):
			t = threading.Thread(target=printer.connect)
			t.daemon = True
			t.start()

		# start up watchdogs
		observer = Observer()
		observer.daemon = True
		observer.schedule(UploadCleanupWatchdogHandler(), s.getBaseFolder("uploads"))
		observer.start()

		#Load additional Tasks
		additionalTasksManager()

		#Load maintenance menu
		maintenanceMenuManager()

		try:
			self._ioLoop = IOLoop.instance()
			self._ioLoop.start()

		except SystemExit:
			pass

		except:
			logger.fatal("Please report this including the stacktrace below in AstroPrint's bugtracker. Thanks!")
			logger.exception("Stacktrace follows:")

		finally:
			observer.stop()
			self.cleanup()
			logger.info('Cleanup complete')

		observer.join(1.0)
		logger.info('Good Bye!')

	def _createSocketConnection(self, session):
		global userManager, eventManager
		return PrinterStateConnection(userManager, eventManager, session)

	def _checkForRoot(self):
		return
		if "geteuid" in dir(os) and os.geteuid() == 0:
			exit("You should not run OctoPrint as root!")

	def _initSettings(self, configfile, basedir):
		settings(init=True, basedir=basedir, configfile=configfile)

	def _initLogging(self, debug, logConf=None):
		defaultConfig = {
			"version": 1,
			"formatters": {
				"simple": {
					"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
				}
			},
			"handlers": {
				"console": {
					"class": "logging.StreamHandler",
					"level": "DEBUG",
					"formatter": "simple",
					"stream": "ext://sys.stdout"
				},
				"file": {
					"class": "logging.handlers.TimedRotatingFileHandler",
					"level": "DEBUG",
					"formatter": "simple",
					"when": "D",
					"backupCount": 5,
					"filename": os.path.join(settings().getBaseFolder("logs"), "astrobox.log")
				},
				"serialFile": {
					"class": "logging.handlers.RotatingFileHandler",
					"level": "DEBUG",
					"formatter": "simple",
					"maxBytes": 2 * 1024 * 1024, # let's limit the serial log to 2MB in size
					"filename": os.path.join(settings().getBaseFolder("logs"), "serial.log")
				}
			},
			"loggers": {
				"SERIAL": {
					"level": "CRITICAL",
					"handlers": ["serialFile"],
					"propagate": False
				}
			},
			"root": {
				"level": "INFO",
				"handlers": ["console", "file"]
			}
		}

		if debug:
			defaultConfig["root"]["level"] = "DEBUG"

		if logConf is None:
			logConf = os.path.join(settings().settings_dir, "logging.yaml")

		configFromFile = {}
		if os.path.exists(logConf) and os.path.isfile(logConf):
			import yaml
			with open(logConf, "r") as f:
				configFromFile = yaml.safe_load(f)

		config = util.dict_merge(defaultConfig, configFromFile)
		logging.config.dictConfig(config)

		if settings().getBoolean(["serial", "log"]):
			# enable debug logging to serial.log
			serialLogger = logging.getLogger("SERIAL")
			serialLogger.setLevel(logging.DEBUG)
			serialLogger.debug("Enabling serial logging")

	def cleanup(self):
		global discoveryManager

		pluginManager().shutdown()
		downloadManager().shutdown()
		printerManager().rampdown()
		discoveryManager.shutdown()
		discoveryManager = None
		boxrouterManager().shutdown()
		cameraManager().shutdown()
		externalDriveManager().shutdown()

		from astroprint.network.manager import networkManagerShutdown
		networkManagerShutdown()

if __name__ == "__main__":
	octoprint = Server()
	octoprint.run()
