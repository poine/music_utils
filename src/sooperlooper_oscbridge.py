#!/usr/bin/env python3
import logging
import threading
import time
#from signal import pause
#from OSC import *
import mido

import liblo

# https://sonosaurus.com/sooperlooper/doc_osc.html
logger = logging.getLogger(__name__)   

import slosc as slo
import smc_mixer as smm
import midi_black as mdb

# physical control (slider, button) response curve 
def scale_input(i, i_min, i_span, rcurve=None):
    o = (i-i_min)/i_span # linearly scale to [0 1]
    if rcurve is not None:
        xc,yc = rcurve
        if o < xc:
            o = o * yc/xc
        else:
            o = yc + (o-xc)*(1-yc)/(1-xc)
    return o

import uinput
class uinputLink:  # emulating keypress
    events = (
        uinput.KEY_VOLUMEDOWN,
        uinput.KEY_VOLUMEUP,
        uinput.KEY_MUTE,
    )
    def __init__(self):
        self.kb_device = uinput.Device(self.events)
        self.counter = 0.
        self.rate = 6.
        
    def change_volume(self, val):
        if 1:
            self.counter += 1 if val > 30 else -1
            logger.debug(f'on_change_volume: {val} {self.counter}')
            if self.counter > self.rate:
                self.counter = 0 
                k = uinput.KEY_VOLUMEDOWN
            elif self.counter < -self.rate:
                self.counter = 0
                k = uinput.KEY_VOLUMEUP
            else:
                return
        else:
            k = uinput.KEY_VOLUMEDOWN if val > 30 else uinput.KEY_VOLUMEUP
        self.kb_device.emit_click(k)
            

class SLBridge(slo.SLOSC):
    
    def __init__(self): # OSC (sooperlooper)
        self.kb_ctl = uinputLink() # we're pretending we're a keyboard to make use of media keys
        smm.SMidi.open_midi()      # SMC Mixer, (midi control surface)
        self.mdb = mdb.MidiBlack() # footswitch
        self.mdb.create_threaded_mainloop(self.on_midi_black_msg)
        slo.SLOSC.__init__(self)   # our sooperlooper osc interface

    def on_midi_black_msg(self, msg):
        #logger.debug(msg)
        if msg.value == 127:
            self.send_cmd(self.CUR_SEL_CHAN, 'hit', 'record')
         
    def on_get_param(self, path, args, types):
        loop_index, param, value = args[0], args[1], args[2]
        logger.debug(f'on_get_param loop_idx:{loop_index}, {param}:{value}')
        if param == 'state':
            self.strip_state[loop_index] = value
            smm.SMidi.set_mute_led(loop_index, value==self.state_muted or value==self.state_undoc1)
            rec_led_state = smm.SMidi.led_off
            if   value == self.state_recording: rec_led_state = smm.SMidi.led_on
            elif value == self.state_wait_start: rec_led_state = smm.SMidi.led_blink_fast
            elif value == self.state_wait_stop: rec_led_state = smm.SMidi.led_blink
            #print(f'set rec state {rec_led_state}')
            smm.SMidi.set_recc_led(loop_index, rec_led_state)
            #smm.SMidi.set_square_led(loop_index, value== self.state_playing)
        elif param == 'is_soloed':
            self.strip_soloed[loop_index] = value
            if not self.strip_soloed[loop_index]: # we're unsoloing, restore mute state
                for i in range(8):
                    if self.strip_saved_state[i] == self.state_muted or self.strip_saved_state[i] == self.state_undoc1:
                        self.send_cmd(i, 'hit', 'mute')

            smm.SMidi.set_solo_led(loop_index, value)
    # def on_pong(self, hosturl, version, loopcount):
    #     _debug_osc(f'on_pong: {hosturl}, {version}, {loopcount}')

    def on_selected(self, path, args, types):
        logger.debug(f'on selected {path} {args} {types}')
        self.cur_sel_loop_id = int(args[2])
        logger.debug(f'on selected2 {self.cur_sel_loop_id}')
        for i in range(smm.SMidi.n_chan):
            smm.SMidi.set_square_led(i,  self.cur_sel_loop_id == i)
            #smm.SMidi.set_strip_selected_led(i,  self.cur_sel_loop_id == i)

    def on_loop_pos(self, path, args, types):
        slo.SLOSC.on_loop_pos(self, path, args, types)
        if self.loop0_rel_pos is not None:
            smm.SMidi.set_sequencer(self.loop0_rel_pos)
            
            
  
    def on_midi_msg(self, msg):
        logger.debug(f'on midi msg: {msg}')
        if smm.SMidi.is_mute_pressed(msg):  # channel mute key
            self.send_cmd(smm.SMidi.muted_channel(msg), 'hit', 'mute')

        elif smm.SMidi.is_slider_move(msg): # slider moved
            chan, val = smm.SMidi.moved_slider_id(msg), scale_input(msg.pitch, -8192, 16384., (0.5, 0.25))
            self.set_param(chan, 'wet', val)
            
        elif smm.SMidi.is_solo_pressed(msg): # channel solo key
            # self.set_global_param('selected_loop_num', smm.SMidi.soloed_channel(msg))
            # for i in range(smm.SMidi.n_chan):
            #     smm.SMidi.set_solo_led(i, i == smm.SMidi.soloed_channel(msg))
            if not self.strip_soloed[smm.SMidi.soloed_channel(msg)]:
                self._save_strip_state()
            self.send_cmd(smm.SMidi.soloed_channel(msg), 'hit', 'solo')
            
            
        elif smm.SMidi.is_recc_pressed(msg): # channel rec key
            self.send_cmd(smm.SMidi.recc_pressed_chan(msg), 'hit', 'record')
        elif smm.SMidi.is_square_pressed(msg): # chneel square
            logger.debug(f'square_pressed')
            #self.send_cmd(smm.SMidi.square_channel(msg), 'hit', 'undo')
            self.set_global_param('selected_loop_num', smm.SMidi.square_channel(msg))
            #for i in range(smm.SMidi.n_chan):
            #    smm.SMidi.set_square_led(i, i == smm.SMidi.square_channel(msg))
            
        elif smm.SMidi.key_pressed1(msg, smm.SMidi.note_playg):# global PLAY key
            self.send_cmd(self.ALL_CHAN if smm.SMidi.is_shifted else self.CUR_SEL_CHAN, 'hit', 'trigger')
        elif smm.SMidi.key_pressed1(msg, smm.SMidi.note_pauseg):# global PAUSE key
            self.send_cmd(self.ALL_CHAN if smm.SMidi.is_shifted else self.CUR_SEL_CHAN, 'hit', 'pause')
        elif smm.SMidi.is_recg_pressed(msg): # global RECORD key
            #self.send_cmd(self.CUR_SEL_CHAN, 'hit', 'record')
            self.send_cmd(self.CUR_SEL_CHAN, 'hit', 'overdub')
        elif smm.SMidi.is_rewind_pressed(msg):# global REWIND key
            self.send_cmd(self.CUR_SEL_CHAN, 'hit', 'undo')
        elif smm.SMidi.is_forward_pressed(msg):# global FORWARD key
            self.send_cmd(self.CUR_SEL_CHAN, 'hit', 'redo')
        elif smm.SMidi.is_right_pressed(msg) :# global RIGHT key
            logger.debug(f'midi_right_press')
            #self.set_global_param('select_next_loop', 1.)
            #self.set_global_param('select_next_loop')
            next_id = self.cur_sel_loop_id + 1
            #if next_id >= self.nb_loops: next_id=0
            if next_id >= 7: next_id=0
            self.set_global_param('selected_loop_num', next_id)
        elif smm.SMidi.is_left_pressed(msg): # global LEFT key
            logger.debug(f'midi_left_press')
            prev_id = self.cur_sel_loop_id - 1
            if prev_id < 0: prev_id=7
            self.set_global_param('selected_loop_num', prev_id)
        elif smm.SMidi.is_up_pressed(msg): # global UP key
            logger.debug(f'midi_up_press')
            smm.SMidi.set_bottom_row_lights(True)
            smm.SMidi.is_shifted = True
        elif smm.SMidi.is_up_released(msg): # global UP key
            logger.debug(f'midi_up_released')
            smm.SMidi.is_shifted = False
            smm.SMidi.set_bottom_row_lights(False)

        elif msg.type=='control_change' and msg.channel==0 and msg.control==16:  # first rotating knob
            logger.debug(f'first knob {msg.value}')
            self.kb_ctl.change_volume(msg.value) # set host volume
        elif msg.type=='control_change' and msg.channel==0 and msg.control==23:  # LAST rotating knob
            logger.debug(f'last knob {msg.value}')
            #self.kb_ctl.change_volume(msg.value)    
            self.set_global_param('wet', float(msg.value)/127.)
             
    def listen_to_midi(self):
        thread = threading.Thread(target=self.periodic)
        thread.start()
        smm.SMidi.loop(self.on_midi_msg)
 
    def periodic(self):
        while True:
            time.sleep(0.25)
            smm.SMidi.periodic()
    
    #smm.SMidi.loop(slb.on_midi_msg)
    # while True:
    #     for msg in smm.SMidi.midi_inport.iter_pending():
    #         _cbk(msg)
    #     #for msg in port.iter_pending():
    #     #print(msg)

    # do_other_stuff()
    
def main():
    logging.basicConfig(level=logging.INFO)
    #logging.getLogger('smc_mixer').setLevel(logging.DEBUG)
    #logging.getLogger('midi_black').setLevel(logging.DEBUG)
    #logging.getLogger('slosc').setLevel(logging.DEBUG)
    #logger.setLevel(logging.DEBUG)
    slb = SLBridge()
    slb.listen_to_midi()
    
    
if __name__ == '__main__':
    main()
