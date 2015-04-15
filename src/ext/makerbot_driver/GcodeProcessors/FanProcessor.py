from __future__ import absolute_import
import re

from . import Processor
import makerbot_driver


class FanProcessor(Processor):

    def __init__(self):
        self.raft_on = re.compile("\(\<setting\> raft Add_Raft,_Elevate_Nozzle,_Orbit: True \</setting\>\)")
        self.raft_end = re.compile("\(\<raftLayerEnd\> \<\/raftLayerEnd\>\)")

        self.layer_start = re.compile("^\(<layer> [0-9.]+.*\)")
        self.layer_end = re.compile("\(\</layer\>\)")
        self.fan_codes = re.compile("[^(;]*[mM]126|[^(;]*[mM]127")
        self.layer_count = 2 # Turn on fan at this layer AFTER The raft
        self.fan_on = "M126 T0 (Fan On)\n"
        self.fan_off = "M127 T0 (Fan Off)\n"


    def check_for_raft(self, code):
        if re.match(self.raft_on, code):
            return True
        else:
            return False


    def check_for_raft_end(self, code):
        if re.match(self.raft_end, code):
            return True
        else:
            return False


    def check_for_layer(self, code):
        if re.match(self.layer_start, code):
            return True
        else:
            return False


    def check_for_layer_end(self, code):
        if re.match(self.layer_end, code):
            return True
        else:
            return False


    def process_gcode(self, gcodes, callback=None):
        """
        This function adds in fan commands to gcode at a specified layer(specified
        by self.layer_count)

        @param gcodes: iterator
        """

        self.checking_for_raft = True
        self.handle_raft = False
        
        layer_count = 0
        for code in gcodes:

            yield code

            if(self.check_for_raft):
                if(self.check_for_layer(code)):
                    self.check_for_raft = False
                elif(self.check_for_raft(code)):
                    self.handle_raft = True
                    self.check_for_raft = False

            if(self.handle_raft):
                while(not self.check_for_raft_end):
                    pass
                self.handle_raft = False
                continue
            else:
                if(self.check_for_layer_end(code)):
                    layer_count += 1
                    if(layer_count == self.layer_count):
                        yield self.fan_on

        yield self.fan_off
