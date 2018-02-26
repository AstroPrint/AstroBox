
import json
import logging

from threading import Thread as thread
from sarge import run, Capture

class GCodeAnalyzer(thread):

	def __init__(self,filename,layersInfo,readyCallback,exceptionCallback,parent):

		self._logger = logging.getLogger(__name__)

		super(GCodeAnalyzer, self).__init__()

		self.filename = filename
		self.readyCallback = readyCallback
		self.exceptionCallback = exceptionCallback
		self.layersInfo = layersInfo
		self.daemon = True

		self.layerList = None
		self.totalPrintTime = None
		self.layerCount = None
		self.size = None
		self.layerHeight = None
		self.totalFilament = None
		self.parent = parent

	def makeCalcs(self):
		self.start()

	def run(self):

		gcodeData = []

		try:
			pipe = run(
				('%s/GCodeAnalyzer "%s" 1' if self.layersInfo else '%s/GCodeAnalyzer "%s"') % (
					'/usr/bin/astroprint',
					self.filename
				), stdout=Capture())

			if pipe.returncode == 0:
				try:
					gcodeData = json.loads(pipe.stdout.text)

					if self.layersInfo:
						self.layerList =  gcodeData['layers']

					self.totalPrintTime = gcodeData['print_time']

					self.layerCount = gcodeData['layer_count']

					self.size = gcodeData['size']

					self.layerHeight = gcodeData['layer_height']

					self.totalFilament = None#total_filament has not got any information

					self.readyCallback(self.layerList,self.totalPrintTime,self.layerCount,self.size,self.layerHeight,self.totalFilament,self.parent)


				except ValueError:
					self._logger.error("Bad gcode data returned: %s" % pipe.stdout.text)
					gcodeData = None

					if self.exceptionCallback:
						parameters = {}
						parameters['parent'] = self.parent
						parameters['filename'] = self.filename

						self.exceptionCallback(parameters)

			else:
				self._logger.warn('Error executing GCode Analyzer')
				gcodeData = None


				if self.exceptionCallback:
					parameters = {}
					parameters['parent'] = self.parent
					parameters['filename'] = self.filename

					self.exceptionCallback(parameters)

		except:
			gcodeData = None

			if self.exceptionCallback:
				parameters = {}
				parameters['parent'] = self.parent
				parameters['filename'] = self.filename

				self.exceptionCallback(parameters)

