#!/usr/bin/env python3
import logging
logger = logging.getLogger(__name__)

import threading, time, mido

PREFIX = 'MIDI Expression BLACK'

class MidiBlack:
    def __init__(self):
        all_in, midi_input_dev = mido.get_input_names(), None
        for indev in all_in:
            if indev.startswith(PREFIX):
                midi_input_dev = indev
                break
        logger.info(f'found midi input {midi_input_dev}')
        all_out, midi_output_dev = mido.get_output_names(), None
        self.midi_inport = mido.open_input(midi_input_dev)
 
    def loop(self):
        for msg in self.midi_inport:
            print(msg) #_cbk(msg)

            
    def create_threaded_mainloop(self, _cbk):
        def _mainloop():
            logger.debug(f'entering mainloop')
            for msg in self.midi_inport:
                logger.debug(f'msg received {msg}')
                _cbk(msg)
        thread = threading.Thread(target=_mainloop)
        thread.start()

        
        
def test_4():
    m = MidiBlack()
    m.loop()

def main():
    logging.basicConfig(level=logging.DEBUG)
    test_4()
               
if __name__ == '__main__':
    main()
