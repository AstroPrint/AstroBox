from __future__ import absolute_import

import re

from . import Processor
import makerbot_driver

class EmptyLayerProcessor(Processor):

    def __init__(self):
        super(EmptyLayerProcessor, self).__init__()
        self.layer_start = re.compile("^\(Slice [0-9.]+.*\)|^\(<layer> [0-9.]+.*\)")
        self.SF_layer_end = re.compile("^\(</layer>\)")
        self.MG_layer_end = re.compile("^\(Slice [0-9.]+.*\)")

        self.move_with_extrude = re.compile("^G1.*[ABE][0-9.-]+.*")
        self.progress = re.compile("^M73")


    def isGenerator(self,iterable):
        """
        Fucntion decides if the input iterable is a generator

        @param iterable: iterable object
        @return boolean: True if it is a generator
        """
        return hasattr(iterable, '__iter__') and not hasattr(iterable, '__len__')


    def process_gcode(self, gcode_in, gcode_info=None):
        """
        Main function for processor, iterates through the input and appends to the output
        what is not in an empty layer

        @param gcode_in: iterable
        @return output: output is a list of processed gcode
        """
        self.progress_in_layer = []
        self.layer_buffer = []
        self.test_if_empty = False
        self.previous_code = ''

        if(self.isGenerator(gcode_in)):
            self.gcode_iter = gcode_in
        else:
            self.gcode_iter = iter(gcode_in)

        for current in self.gcode_iter:
            self.init_moves = 0

            self.handle_layer_start_check(self.previous_code, current)

            if(self.test_if_empty):
                self.test_if_empty = False
                if(self.layer_test_if_empty(self.init_moves)):
                    #if layer is empty just append the progress
                    for item in self.progress_in_layer: yield item
                else:
                    #if layer is not empty add it to the output
                    for item in self.layer_buffer: yield item
                self.progress_in_layer = []
                self.layer_buffer = []
            else:
                yield current


    def handle_layer_start_check(self, previous_code, current_code):
        """
        Checks if the current or previous code is a new layer and handles it accordingly

        This function is mostly for Miracle-Grue as it does not have a layer end comment

        @param previous_code: gcode_string from the previous iteration (this is used for MG)
        @param current_code: gcode string
        """
        if(self.check_for_layer_start(current_code)):
            self.test_if_empty = True
            self.layer_buffer.append(current_code)
        elif(self.check_for_layer_start(previous_code)):
            self.test_if_empty = True
            self.layer_buffer.append(previous_code)
            self.layer_buffer.append(current_code)
            if(self.check_for_move_with_extrude(current_code)):
                self.init_moves = 1


    def layer_test_if_empty(self, init_moves):
        """
        Iterates through a the gcode layer until the layer ends or EOF.
        It counts the number of moves with extrude commands in the layer,
        and decides if a layer is empty base on that number.

        @param init_moves: the inital moves_with_extrude in the layer (used for Miracle-Grue)
        @return boolean: True if the layer is empty
        """
        moves_with_extrude = init_moves

        for current in self.gcode_iter:
            #put progress lines in a second list (buffer), if the slice is empty they
            #will be added to the output
            if(self.check_for_progress(current)):
                self.progress_in_layer.append(current)
            elif(self.check_for_move_with_extrude(current)):
                moves_with_extrude += 1
            rv = self.check_for_layer_end(current)
            if(rv != None):
                if(rv == 'mg'):
                    pass
                    #Save the current code since it is most likely a slice header
                    self.previous_code = current
                elif(rv == 'sf'):
                    self.layer_buffer.append(current)
                break

            self.layer_buffer.append(current)

        if(moves_with_extrude > 0):
            return False
        else:
            return True
            

    def check_for_move_with_extrude(self, string):
        match = re.match(self.move_with_extrude, string)
        return match is not None


    def check_for_layer_start(self, string):
        match = re.match(self.layer_start, string)
        return match is not None


    def check_for_layer_end(self, string):
        match = re.match(self.MG_layer_end, string)
        if match is not None:
            return 'mg'
        match = re.match(self.SF_layer_end, string)
        if match is not None:
            return 'sf'
        else:
            return None


    def check_for_progress(self, string):
        match = re.match(self.progress, string)
        return match is not None


