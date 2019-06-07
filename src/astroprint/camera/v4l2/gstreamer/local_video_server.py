#!/usr/bin/env python

# MIT License
# (c) 2017 Kevin J. Walchko

from __future__ import print_function
import cv2
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import time
import argparse
from opencvutils import Camera
import socket as Socket
from opencvutils import __version__ as VERSION
# import errno
import os
import re

# I use to do 0.0.0.0 to bind to all interfaces, but that seemed to be really
# slow. feeding it the correct ip address seems to greatly speed things up.


camera = None


def getIP(iface):
	search_str = 'ip addr show wlan0'.format(iface)
	ipv4 = re.search(re.compile(r'(?<=inet )(.*)(?=\/)', re.M), os.popen(search_str).read()).groups()[0]
	ipv6 = re.search(re.compile(r'(?<=inet6 )(.*)(?=\/)', re.M), os.popen(search_str).read()).groups()[0]
	return (ipv4, ipv6)


def setUpCameraPi(win=(320, 240)):
	global camera
	camera = Camera('pi')
	camera.init(win=win)


def setUpCameraCV(win=(320, 240), cv=0):
	global camera
	camera = Camera('cv')
	camera.init(cameraNumber=cv, win=win)


def compress(orig, comp):
	return float(orig) / float(comp)


class mjpgServer(BaseHTTPRequestHandler):
	"""
	A simple mjpeg server that either publishes images directly from a camera
	or republishes images from another pygecko process.
	"""

	ip = None
	hostname = None

	def do_GET(self):
		global camera
		print('connection from:', self.address_string())

		if self.ip is None or self.hostname is None:
			self.ip, _ = getIP('wlan0')
			self.hostname = Socket.gethostname()

		if self.path == '/mjpg':
			self.send_response(200)
			self.send_header(
				'Content-type',
				'multipart/x-mixed-replace; boundary=--jpgboundary'
			)
			self.end_headers()

			while True:
				if camera:
					# print('cam')
					ret, img = camera.read()

				else:
					raise Exception('Error, camera not setup')

				if not ret:
					print('no image from camera')
					time.sleep(1)
					continue

				ret, jpg = cv2.imencode('.jpg', img)
				# print 'Compression ratio: %d4.0:1'%(compress(img.size,jpg.size))
				self.wfile.write("--jpgboundary")
				self.send_header('Content-type', 'image/jpeg')
				# self.send_header('Content-length',str(tmpFile.len))
				self.send_header('Content-length', str(jpg.size))
				self.end_headers()
				self.wfile.write(jpg.tostring())
				# time.sleep(0.05)

		elif self.path == '/':
			# hn = self.server.server_address[0]
			port = self.server.server_address[1]
			ip = self.ip
			hostname = self.hostname

			self.send_response(200)
			self.send_header('Content-type', 'text/html')
			self.end_headers()
			self.wfile.write('<html><head></head><body>')
			self.wfile.write('<h1>{0!s}[{1!s}]:{2!s}</h1>'.format(hostname, ip, port))
			self.wfile.write('<img src="http://{}:{}/mjpg"/>'.format(ip, port))
			self.wfile.write('<p>{0!s}</p>'.format((self.version_string())))
			# self.wfile.write('<p>The mjpg stream can be accessed directly at:<ul>')
			# self.wfile.write('<li>http://{0!s}:{1!s}/mjpg</li>'.format(ip, port))
			# self.wfile.write('<li><a href="http://{0!s}:{1!s}/mjpg"/>http://{0!s}:{1!s}/mjpg</a></li>'.format(hostname, port))
			# self.wfile.write('</p></ul>')
			self.wfile.write('<p>This only handles one connection at a time</p>')
			self.wfile.write('</body></html>')

		else:
			print('error', self.path)
			self.send_response(404)
			self.send_header('Content-type', 'text/html')
			self.end_headers()
			self.wfile.write('<html><head></head><body>')
			self.wfile.write('<h1>{0!s} not found</h1>'.format(self.path))
			self.wfile.write('</body></html>')


def handleArgs():
	parser = argparse.ArgumentParser(version=VERSION, description='A simple mjpeg server Example: mjpeg-server -p 8080 --camera 4')
	parser.add_argument('-p', '--port', help='mjpeg publisher port, default is 9000', type=int, default=9000)
	parser.add_argument('-c', '--camera', help='set opencv camera number, ex. -c 1', type=int, default=0)
	parser.add_argument('-t', '--type', help='set camera type, either pi or cv, ex. -t pi', default='cv')
	parser.add_argument('-s', '--size', help='set size', nargs=2, type=int, default=(320, 240))

	args = vars(parser.parse_args())
	args['size'] = (args['size'][0], args['size'][1])
	return args


def main():
	args = handleArgs()

	try:
		win = args['size']
		if args['type'] is 'cv':
			cv = args['camera']
			setUpCameraCV(cv=cv, win=win)
		else:
			setUpCameraPi(win=win)
		# server = HTTPServer(('0.0.0.0', args['port']), mjpgServer)
		ipv4, ipv6 = getIP('wlan0')
		print('wlan0:', ipv4)
		mjpgServer.ip = ipv4
		mjpgServer.hostname = Socket.gethostname()
		server = HTTPServer((ipv4, args['port']), mjpgServer)
		print("server started on {}:{}".format(Socket.gethostname(), args['port']))
		server.serve_forever()

	except KeyboardInterrupt:
		print('KeyboardInterrupt')

	server.socket.close()


if __name__ == '__main__':
	main()
