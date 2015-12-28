# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import uuid
import flask
import json
import tornado.wsgi
from sockjs.tornado import SockJSRouter
from flask import Flask, render_template, send_from_directory, make_response, Response, request
from flask.ext.login import LoginManager, current_user, logout_user
from flask.ext.principal import Principal, Permission, RoleNeed, identity_loaded, UserNeed
from flask.ext.compress import Compress
from flask.ext.assets import Environment
from watchdog.observers import Observer
from sys import platform

import os
import time
import logging
import logging.config

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

principals = Principal(app)
admin_permission = Permission(RoleNeed("admin"))
user_permission = Permission(RoleNeed("user"))

# only import the octoprint stuff down here, as it might depend on things defined above to be initialized already
from octoprint.server.util import LargeResponseHandler, ReverseProxied, restricted_access, PrinterStateConnection, admin_validator, \
	UrlForwardHandler, user_validator
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
from astroprint.printerprofile import printerProfileManager
from astroprint.variant import variantManager
from astroprint.discovery import DiscoveryManager

UI_API_KEY = ''.join('%02X' % ord(z) for z in uuid.uuid4().bytes)
VERSION = None

@app.route('/astrobox/identify', methods=['GET'])
def box_identify():
	br = boxrouterManager()
	nm = networkManager()

	response = Response()

	response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
	response.data = json.dumps({
		'id': br.boxId,
		'name': nm.getHostname(),
		'version': VERSION
	})

	return response

@app.route("/")
def index():
	s = settings()
	loggedUsername = s.get(["cloudSlicer", "loggedUser"])

	if (s.getBoolean(["server", "firstRun"])):
		# we need to get the user to sign into their AstroPrint account
		return render_template(
			"setup.jinja2",
			debug= debug,
			uiApiKey= UI_API_KEY,
			version= VERSION,
			variantData= variantManager().data,
			astroboxName= networkManager().getHostname(),
			settings=s
		)

	elif softwareManager.updatingRelease or softwareManager.forceUpdateInfo:
		return render_template(
			"updating.jinja2",
			uiApiKey= UI_API_KEY,
			showForceUpdate=  softwareManager.forceUpdateInfo != None,
			releaseInfo= softwareManager.updatingRelease or softwareManager.forceUpdateInfo,
			lastCompletionPercent= softwareManager.lastCompletionPercent,
			lastMessage= softwareManager.lastMessage,
			variantData= variantManager().data,
			astroboxName= networkManager().getHostname()
		)

	elif loggedUsername and (current_user is None or not current_user.is_authenticated() or current_user.get_id() != loggedUsername):
		if current_user.is_authenticated():
			logout_user()

		return render_template(
			"locked.jinja2",
			username= loggedUsername,
			uiApiKey= UI_API_KEY,
			astroboxName= networkManager().getHostname(),
			variantData= variantManager().data
		)

	else:
		pm = printerManager()
		nm = networkManager()

		paused = pm.isPaused()
		printing = pm.isPrinting()
		online = nm.isOnline()

		return render_template(
			"app.jinja2",
			user_email= loggedUsername,
			version= VERSION,
			printing= printing,
			paused= paused,
			online= online,
			print_capture= cameraManager().timelapseInfo if printing or paused else None,
			printer_profile= printerProfileManager().data,
			uiApiKey= UI_API_KEY,
			astroboxName= nm.getHostname(),
			variantData= variantManager().data,
			serialLogActive= s.getBoolean(['serial', 'log'])
		)

@app.route("/discovery.xml")
def discoveryXml():
	response = flask.make_response( discoveryManager().getDiscoveryXmlContents() )
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
def camera_snapshot():
	cameraMgr = cameraManager()
	pic_buf = cameraMgr.get_pic(text=request.args.get('text'))
	if pic_buf:
		return Response(pic_buf, mimetype='image/jpeg')
	else:
		return 'Camera not ready', 404

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


	def run(self):
		if not self._allowRoot:
			self._checkForRoot()

		global userManager
		global eventManager
		global loginManager
		global debug
		global softwareManager
		global VERSION

		from tornado.wsgi import WSGIContainer
		from tornado.httpserver import HTTPServer
		from tornado.ioloop import IOLoop
		from tornado.web import Application, FallbackHandler

		from astroprint.printfiles.watchdogs import UploadCleanupWatchdogHandler

		debug = self._debug

		# first initialize the settings singleton and make sure it uses given configfile and basedir if available
		self._initSettings(self._configfile, self._basedir)
		s = settings()

		# then initialize logging
		self._initLogging(self._debug, self._logConf)
		logger = logging.getLogger(__name__)

		if s.getBoolean(["accessControl", "enabled"]):
			userManagerName = settings().get(["accessControl", "userManager"])
			try:
				clazz = util.getClass(userManagerName)
				userManager = clazz()
			except AttributeError, e:
				logger.exception("Could not instantiate user manager %s, will run with accessControl disabled!" % userManagerName)

		softwareManager = swManager()
		VERSION = softwareManager.versionString

		logger.info("Starting AstroBox (%s)" % VERSION)

		eventManager = events.eventManager()
		printer = printerManager(printerProfileManager().data['driver'])

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

		self._discovery = DiscoveryManager()

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
					app.session_interface.open_session(app, flask.request)
					loginManager.reload_user()
					validator(flask.request)
			return f

		self._tornado_app = Application(self._router.urls + [
			(r"/downloads/timelapse/([^/]*\.mpg)", LargeResponseHandler, {"path": s.getBaseFolder("timelapse"), "as_attachment": True}),
			(r"/downloads/files/local/([^/]*\.(gco|gcode))", LargeResponseHandler, {"path": s.getBaseFolder("uploads"), "as_attachment": True}),
			(r"/downloads/logs/([^/]*)", LargeResponseHandler, {"path": s.getBaseFolder("logs"), "as_attachment": True, "access_validation": access_validation_factory(admin_validator)}),
			(r"/downloads/camera/current", UrlForwardHandler, {"url": s.get(["webcam", "snapshot"]), "as_attachment": True, "access_validation": access_validation_factory(user_validator)}),
			(r".*", FallbackHandler, {"fallback": WSGIContainer(app.wsgi_app)})
		])
		self._server = HTTPServer(self._tornado_app)
		self._server.listen(self._port, address=self._host)

		logger.info("Listening on http://%s:%d" % (self._host, self._port))

		eventManager.fire(events.Events.STARTUP)
		if s.getBoolean(["serial", "autoconnect"]):
			(port, baudrate) = s.get(["serial", "port"]), s.getInt(["serial", "baudrate"])
			connectionOptions = printer.getConnectionOptions()
			if port in connectionOptions["ports"]:
				printer.connect(port, baudrate)

		# start up watchdogs
		observer = Observer()
		observer.schedule(UploadCleanupWatchdogHandler(), s.getBaseFolder("uploads"))
		observer.start()

		try:
			IOLoop.instance().start()
		except SystemExit:
			self.cleanup()
		except:
			logger.fatal("Please report this including the stacktrace below in AstroPrint's bugtracker. Thanks!")
			logger.exception("Stacktrace follows:")
		finally:
			observer.stop()
		observer.join()

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
			logging.getLogger("SERIAL").setLevel(logging.DEBUG)
			logging.getLogger("SERIAL").debug("Enabling serial logging")

	def cleanup(self):
		self._discovery.shutdown()
		self._discovery = None
		boxrouterManager().shutdown()
		logging.getLogger(__name__).info("Goodbye!")

if __name__ == "__main__":
	octoprint = Server()
	octoprint.run()
