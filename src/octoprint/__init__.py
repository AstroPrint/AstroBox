#!/usr/bin/env python
import sys

from octoprint.daemon import Daemon
from octoprint.server import Server
from signal import signal, SIGTERM, SIGINT

astrobox = None

if 'linux' in sys.platform:
	import dbus.mainloop.glib

	dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
	dbus.mainloop.glib.threads_init()

#~~ main class

class Main(Daemon):
	def __init__(self, pidfile, configfile, basedir, host, port, debug, allowRoot, logConf):
		Daemon.__init__(self, pidfile)

		self._configfile = configfile
		self._basedir = basedir
		self._host = host
		self._port = port
		self._debug = debug
		self._allowRoot = allowRoot
		self._logConf = logConf

	def run(self):
		startServer(self._configfile, self._basedir, self._host, self._port, self._debug, self._allowRoot)

def main():
	import argparse

	parser = argparse.ArgumentParser(prog="run")

	parser.add_argument("-v", "--version", action="store_true", dest="version",
						help="Output AstroBox's version and exit")

	parser.add_argument("-d", "--debug", action="store_true", dest="debug",
						help="Enable debug mode")

	parser.add_argument("--host", action="store", type=str, dest="host",
						help="Specify the host on which to bind the server")
	parser.add_argument("--port", action="store", type=int, dest="port",
						help="Specify the port on which to bind the server")

	parser.add_argument("-c", "--config", action="store", dest="config",
						help="Specify the config file to use. AstroBox needs to have write access for the settings dialog to work. Defaults to /etc/astrobox/config.yaml")
	parser.add_argument("-b", "--basedir", action="store", dest="basedir",
						help="Specify the basedir to use for uploads, timelapses etc. AstroBox needs to have write access. Defaults to /etc/astrobox")
	parser.add_argument("--logging", action="store", dest="logConf",
						help="Specify the config file to use for configuring logging. Defaults to /etc/astrobox/logging.yaml")

	parser.add_argument("--daemon", action="store", type=str, choices=["start", "stop", "restart"],
						help="Daemonize/control daemonized AstroBox instance (only supported under Linux right now)")
	parser.add_argument("--pid", action="store", type=str, dest="pidfile", default="/tmp/astrobox.pid",
						help="Pidfile to use for daemonizing, defaults to /tmp/astrobox.pid")

	parser.add_argument("--iknowwhatimdoing", action="store_true", dest="allowRoot",
						help="Allow AstroBox to run as user root")

	args = parser.parse_args()

	if args.version:
		print "AstroBox version %s" % __version__
		sys.exit(0)

	if args.daemon:
		if sys.platform == "darwin" or sys.platform == "win32":
			print >> sys.stderr, "Sorry, daemon mode is only supported under Linux right now"
			sys.exit(2)

		daemon = Main(args.pidfile, args.config, args.basedir, args.host, args.port, args.debug, args.allowRoot, args.logConf)
		if "start" == args.daemon:
			daemon.start()
		elif "stop" == args.daemon:
			daemon.stop()
		elif "restart" == args.daemon:
			daemon.restart()
	else:
		startServer(args.config, args.basedir, args.host, args.port, args.debug, args.allowRoot, args.logConf)

def startServer(configfile, basedir, host, port, debug, allowRoot, logConf = None):
	signal(SIGTERM, lambda signum, stack_frame: sys.exit(1)) #Redirects "nice" kill commands to SystemExit exception
	signal(SIGINT, lambda signum, stack_frame: sys.exit(1)) #Redirects CTRL+C to SystemExit exception

	global astrobox

	astrobox = Server(configfile, basedir, host, port, debug, allowRoot, logConf)

	astrobox.run()

if __name__ == "__main__":
	main()
