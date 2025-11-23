#!/usr/bin/env python3
import logging
import threading, time, mido

CTL_PREFIX = 'SINCO:SINCO SMC-Mixer-Master'

logger = logging.getLogger(__name__)

class SMidi:
    n_chan     = 8 

    note_rec   = 0
    note_solo  = 8
    note_mute  = 16
    note_sqr   = 24
    note_foo1  = 40
    
    note_playg  = 94
    note_pauseg = 93
    note_recg   = 95
    note_REWIND = 91
    note_FORWARD = 92
    note_FFORWARD = 46
    note_FREWIND  = 47
    note_UP     = 96
    note_DOWN   = 97
    note_LEFT   = 98
    note_RIGHT  = 99

    

    mode_user, mode_daw = 0, 1
    mode = mode_daw
    is_shifted = False # a shift using UP key
    
    strip_fader = [0]*n_chan
    def set_strip_fader(chan, val): SMidi.strip_fader[chan] = val
    def get_strip_fader(chan): return SMidi.strip_fader[chan]

    led_off, led_on, led_blink, led_blink_fast = 0, 1, 2, 3

    led_mute_state = [led_off]*n_chan
    led_mute_blink_state = [True]*n_chan

    led_rec_state = [led_off]*n_chan
    led_rec_blink_state = [True]*n_chan

    sequencer_led_idx = None
    sequencer_prev_led_idx = None
    sequencer_size = 8
    sequencer_led_id = [note_REWIND, note_FORWARD, note_FREWIND, note_FFORWARD,
                        note_UP, note_DOWN, note_LEFT, note_RIGHT ]
    
    periodic_count = 0
    
    def key_pressed(msg): return msg.type == 'note_on' and msg.velocity == 127
    def key_pressed1(msg, note): return SMidi.key_pressed(msg) and msg.note == note
    def key_released(msg): return msg.type == 'note_on' and msg.velocity == 0
    def key_released1(msg, note): return SMidi.key_released(msg) and msg.note == note
    
    def chan(msg, note): return msg.note - note
    def key_pressed_range(msg, note):
        return SMidi.key_pressed(msg) and SMidi.chan(msg, note) >= 0 and SMidi.chan(msg, note) < SMidi.n_chan

    def set_led(led_id, state):
        SMidi.send(mido.Message('note_on', note=led_id, velocity=127 if state in [SMidi.led_on,SMidi.led_blink] else 0))
    
    def is_solo_pressed(msg):
        #_debug_midi(f'in solo pressed {SMidi.key_pressed_range(msg, SMidi.note_solo) if msg.type == "note_on" else {msg.type}}')
        return SMidi.key_pressed_range(msg, SMidi.note_solo )
    def soloed_channel(msg): return msg.note - SMidi.note_solo
    def set_solo_led(ch_id, state): SMidi.send(mido.Message('note_on', note=SMidi.note_solo+ch_id, velocity=127 if state else 0))

    def set_strip_selected_led(strip_id, state):
        if not state: pitch = SMidi.get_strip_fader(strip_id)
        else:
            pitch = 8191 if SMidi.get_strip_fader(strip_id) < 0 else -8192
        #msg = mido.Message('pitchwheel', channel=strip_id, pitch=8191 if state else -8192, time=0)
        msg = mido.Message('pitchwheel', channel=strip_id, pitch=pitch, time=0)
        SMidi.send(msg) 


    
    def is_recc_pressed(msg):
        #_debug_midi(f'in recc pressed {SMidi.key_pressed_range(msg, SMidi.note_rec)}')
        return SMidi.key_pressed_range(msg, SMidi.note_rec)
    def recc_pressed_chan(msg): return SMidi.chan(msg, SMidi.note_rec)
    def set_recc_led(ch_id, state):
        #print(f'set_recc_state {ch_id} {state}')
        SMidi.led_rec_state[ch_id] = state
        #breakpoint()
        SMidi.send(mido.Message('note_on', note=SMidi.note_rec+ch_id, velocity=127 if state in [SMidi.led_on,SMidi.led_blink] else 0))
    def toggle_recc_led(ch_id):
        #print('in toggle')
        SMidi.led_rec_blink_state[ch_id] = not SMidi.led_rec_blink_state[ch_id]
        SMidi.send(mido.Message('note_on', note=SMidi.note_rec+ch_id, velocity=127 if SMidi.led_rec_blink_state[ch_id] else 0))

    def is_mute_pressed(msg):
        if SMidi.mode == SMidi.mode_user:
            pressed = msg.type == 'control_change' and msg.control >=20 and msg.control< 28 and msg.value==127
            chan =  msg.control - 20 if pressed else -1
        else:
            pressed = SMidi.key_pressed_range(msg, SMidi.note_mute)
            chan =  SMidi.chan(msg, SMidi.note_mute) if pressed else -1
        #if pressed: _debug_midi(f'mute_is_pressed on {chan}')
        return pressed
    #def muted_channel(msg): return SMidi.chan(msg, SMidi.note_mute)
    def muted_channel(msg): return msg.control - 20 if SMidi.mode == SMidi.mode_user else SMidi.chan(msg, SMidi.note_mute)
    def set_mute_led(ch_id, state): SMidi.send(mido.Message('note_on', note=SMidi.note_mute+ch_id, velocity=127 if state else 0))
    # def set_mute_led(ch_id, state):
    #     if SMidi.mode == SMidi.mode_user:
    #         SMidi.send(mido.Message('control_change', channel=0, control=20+ch_id, value=127 if state else 0))
    #     else:
    #         SMidi.send(mido.Message('note_on', note=SMidi.note_mute+ch_id, velocity=127 if state else 0))
 
    def is_square_pressed(msg): return SMidi.key_pressed_range(msg, SMidi.note_sqr)
    def square_channel(msg): return SMidi.chan(msg, SMidi.note_sqr)
    def set_square_led(ch_id, state):
        SMidi.send(mido.Message('note_on', note=SMidi.note_sqr+ch_id, velocity=127 if state else 0))
        
    def is_down_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_DOWN)
    def is_up_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_UP)
    def is_up_released(msg): return SMidi.key_released1(msg, SMidi.note_UP)
    def is_left_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_LEFT)
    def is_right_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_RIGHT)

    def is_slider_move(msg): return msg.type == 'pitchwheel'
    def moved_slider_id(msg): return msg.channel
    

    def is_recg_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_recg)


    def is_rewind_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_REWIND) 
    def is_forward_pressed(msg): return SMidi.key_pressed1(msg, SMidi.note_FORWARD) 

    def set_bottom_row_lights(state):
        SMidi.send(mido.Message('note_on', note=SMidi.note_playg,  velocity=127 if state else 0))
        SMidi.send(mido.Message('note_on', note=SMidi.note_pauseg, velocity=127 if state else 0))

    def set_sequencer(value):
        SMidi.sequencer_prev_led_idx = SMidi.sequencer_led_idx
        SMidi.sequencer_led_idx  = int(value*8)
        #logger.debug(f'set_sequencer {value} {SMidi.sequencer_led_idx} {SMidi.sequencer_prev_led_idx}')
        if SMidi.sequencer_led_idx != SMidi.sequencer_prev_led_idx:
            for i in range(SMidi.sequencer_size):
               SMidi.set_led(SMidi.sequencer_led_id[i], state=SMidi.led_on if i<=SMidi.sequencer_led_idx else 0)
        
    def open_midi(): # Midi communication
        all_in, midi_input_dev = mido.get_input_names(), None
        for indev in all_in:
            if indev.startswith(CTL_PREFIX):
                midi_input_dev = indev
                break
        logger.info(f'found midi input {midi_input_dev}')
        all_out, midi_output_dev = mido.get_output_names(), None
        for outdev in all_out:
            if outdev.startswith(CTL_PREFIX):
                midi_output_dev = outdev
                break
        logger.info(f'found midi ouput {midi_output_dev}')
        SMidi.midi_inport = mido.open_input(midi_input_dev)
        SMidi.midi_outport = mido.open_output(midi_output_dev)

    def send(msg): 
        logger.debug(f'sending {msg}')
        SMidi.midi_outport.send(msg)


    def loop(_cbk):
        for msg in SMidi.midi_inport:
            _cbk(msg)
            
    def periodic():
        SMidi.periodic_count+=1
        #print(f'in midi periodic {SMidi.led_rec_state} {SMidi.led_rec_blink_state}')
        for i in range(SMidi.n_chan):
            if (SMidi.led_rec_state[i] == SMidi.led_blink_fast or
               (SMidi.led_rec_state[i] == SMidi.led_blink and SMidi.periodic_count % 2)):
               SMidi.toggle_recc_led(i)


def test_1_switch_led(on=True, chan=0):
    for i in range(128):
        SMidi.send(mido.Message('note_on',  channel=chan, note=i, velocity=127 if on else 0, time=0))
        time.sleep(0.1)

def test_2_cc():
    msg = mido.Message('control_change', channel=0, control=16, value=1, time=0)
    #control_change channel=0 control=16 value=1 time=0
    print(f'sending {msg}')
    SMidi.send(msg) 
    time.sleep(1)

def test_3_pw(on=False):
    for i in range(8):
        if 0:
            msg = mido.Message('pitchwheel', channel=i, pitch=8191 if on else -8192, time=0)
            SMidi.send(msg)
        else:
            SMidi.set_strip_selected_led(i,  True)
        time.sleep(0.01)
    time.sleep(1.)
    for i in range(8):
        SMidi.set_strip_selected_led(i,  False)
        time.sleep(0.01)
        
def test_dump():
    def _cbk(msg):
        print(msg)
    SMidi.loop(_cbk)

def test_sequencer():
    def _cbk(msg):
        print(msg)
    SMidi.loop(_cbk)


    
class SMCMixer:
    # user mode rewrite?
    def __init__(self):
        pass
    
    def connect(self): # Midi communication
        all_in, midi_input_dev = mido.get_input_names(), None
        for indev in all_in:
            if indev.startswith(CTL_PREFIX):
                midi_input_dev = indev
                break
        logger.info(f'found midi input {midi_input_dev}')
        all_out, midi_output_dev = mido.get_output_names(), None
        for outdev in all_out:
            if outdev.startswith(CTL_PREFIX):
                midi_output_dev = outdev
                break
        logger.info(f'found midi ouput {midi_output_dev}')
        self.midi_inport = mido.open_input(midi_input_dev)
        self.midi_outport = mido.open_output(midi_output_dev)
        logger.debug(f'opened {midi_input_dev} and {midi_output_dev}')

    def send(self, msg): 
        logger.debug(f'sending {msg}')
        self.midi_outport.send(msg)
        
    def loop(self, _cbk):
        for msg in self.midi_inport:
            _cbk(msg)
    



            
def test_user_mode_1():
    m = SMCMixer()
    m.connect()
    
    chan, note, on = 0, 97, True
    #for i in range(128):
    m.send(mido.Message('note_on',  channel=chan, note=note, velocity=127 if on else 0, time=0))
    #m.send(mido.Message('control_change', channel=1, control=60, value=127, time=0))
    time.sleep(0.1)

    def on_msg(msg):
        print(msg)
    m.loop(on_msg)
        
def main():
    logging.basicConfig(level=logging.DEBUG)
    if 1:
        SMidi.open_midi()
        test_1_switch_led()
        #test_2_cc()
        #test_3_pw()
        #test_dump()
    else:
        test_user_mode_1()
               
if __name__ == '__main__':
    main()
