#!/usr/bin/env python3
#
## sooperlooper osc protocol
#

# https://sonosaurus.com/sooperlooper/doc_osc.html
import time
import argparse
import logging
import liblo

SL_HOST = 'localhost'
SL_HOST = '127.0.0.1'
SL_PORT = 9951
SL_URL = f'osc.udp://{SL_HOST}:{SL_PORT}'

logger = logging.getLogger(__name__)

class SLOSC:

    state_unknown     = -1
    state_off         =  0
    state_wait_start  =  1
    state_recording   =  2
    state_wait_stop   =  3
    state_playing     =  4
    state_muted       = 10
    state_paused      = 14
    state_undoc1      = 20

    strip_state = [state_unknown]*8
    strip_saved_state = [state_unknown]*8
    strip_soloed = [False]*8

    loop0_len = None
    loop0_rel_pos = None
    
    channel_all = -1
    channel_sel = -3
    ALL_CHAN = -1
    CUR_SEL_CHAN = -3

    def _save_strip_state(self):
        for i in range(8): self.strip_saved_state[i] = self.strip_state[i] 
    
    def __init__(self):

        self.cur_sel_loop_id = 0 # cache that to emulate next_loop with selected_loop. workaround
        self.nb_loops = 1

        self.target = liblo.Address(SL_HOST, SL_PORT)
        self.st = liblo.ServerThread()
        self.st.add_method('/param', 'isf', self.on_get_param)
        self.st.add_method('/loop_pos', 'isf', self.on_loop_pos)
        self.st.add_method('/selected', 'isf', self.on_selected)
        self.st.add_method('/pong', 'ssi', self.on_pong)
        self.st.add_method('/load_err', 's', self.on_load)
        self.url = self.st.get_url()
        self.register_updates()
        self.st.start()
        self.send_ping()

    def register_updates(self, n_chan=8):
        logger.debug(f'register updates')
        for i in range(n_chan):
            liblo.send(self.target, f'/sl/{i}/register_auto_update', ('s', 'state') , ('i', 100), ('s', f'{self.url}'), ('s', '/param'))
            liblo.send(self.target, f'/sl/{i}/register_auto_update', ('s', 'is_soloed') , ('i', 100), ('s', f'{self.url}'), ('s', '/param'))
        liblo.send(self.target, f'/register_auto_update', ('s', 'selected_loop_num'), ('i', 100), ('s', f'{self.url}'), ('s', '/selected'))

        # get position of first loop (sync channel)
        liblo.send(self.target, f'/sl/{0}/register_auto_update', ('s', 'loop_pos') , ('i', 100), ('s', f'{self.url}'), ('s', '/loop_pos'))
        liblo.send(self.target, f'/sl/{0}/register_auto_update', ('s', 'loop_len') , ('i', 100), ('s', f'{self.url}'), ('s', '/loop_pos'))
        
    def on_load(self, blah):
        logger.debug(f'on_load: {blah}')

    def load_session(self, filename):
        error_path = '/err_load'
        logger.debug(f'sending load_session {filename}, {self.url}, {error_path}')
        #liblo.send(self.target, "/load_session", filename, self.url, error_path)
        liblo.send(self.target, "/load_session", ('s', filename), ('s', self.url), ('s', error_path))
        #  /load_session   s:filename  s:return_url  s:error_path

    def save_session(self, filename):
        error_path = '/err_save'
        logger.debug(f'sending save_session {filename}, {self.url}, {error_path}')
        #liblo.send(self.target, "/save_session", filename, self.url, error_path)
        liblo.send(self.target, "/save_session", ('s', filename), ('s', self.url), ('s', error_path))
        
    def send_ping(self):
        logger.debug(f'sending ping')
        liblo.send(self.target, f'/ping', ('s', f'{self.url}'), ('s', '/pong'))
      
    def send_cmd(self, lp, tp, cmd):
        logger.debug(f'sending to sl: {lp} {tp} {cmd}')
        liblo.send(self.target, f'/sl/{lp}/{tp}', ('s', f'{cmd}'))

    def get_param(self, lp, ctl, path='/param'):
        #/sl/#/get  s:control  s:return_url  s: return_path
        # Which returns an OSC message to the given return url and path with the arguments:
        #i:loop_index  s:control  f:value
        liblo.send(self.target, f'/sl/{lp}/get', ('s', f'{ctl}'), ('s', f'{self.url}'), ('s', path))

    def set_param(self, lp, ctl, val):
        liblo.send(self.target, f'/sl/{lp}/set', ('s', f'{ctl}'), ('f', f'{val}')) 

    def set_global_param(self, prm, val=None):
        if 0:
            cmd, args = f"/set", (('s', f'{prm}'),)
            if val is not None: args += (('f', f'{val}'),)
            logger.debug(f'set_global_param {cmd} {args}')
            liblo.send(self.target, cmd, *args)
        else:
            liblo.send(self.target, f'/set', ('s', f'{prm}'), ('f', f'{val}'))

    def on_pong(self, path, args, types):
        hosturl, version, loopcount = args
        logger.debug(f'on_pong: {hosturl}, {version}, {loopcount}')
        logger.info(f'found soopelooper at : {hosturl} (v{version}), with {loopcount} loops')
        self.__nb_loops = loopcount
        # self.get_param(0, 'loop_len')

    def on_get_param(self, path, args, types):
        loop_index, param, value = args[0], args[1], args[2]
        logger.debug(f'on_get_param loop_idx:{loop_index}, {param}:{value}')

    def on_selected(self, path, args, types):
        logger.debug(f'on selected {path} {args} {types}')
        sel_loop_id = int(args[2])

    def on_loop_pos(self, path, args, types):
        #logger.debug(f'on loop_pos {path} {args} {types}')
        loop_id, param, value = int(args[0]), args[1], float(args[2])
        #logger.debug(f'on loop_pos {loop_id} {param} {value}')
        if param == 'loop_len':
            self.loop0_len = value
            #logger.debug(f'on_loop_pos loop_len {self.loop0_len}')
        elif param == 'loop_pos':
            if self.loop0_len is not None and self.loop0_len != 0:
                self.loop0_rel_pos = value/self.loop0_len
                logger.debug(f'on loop_pos {self.loop0_rel_pos*100:.01f}%')

                  
    def new_session(self):
        pass

def cli(s):
    parser = argparse.ArgumentParser(
        prog='slosc',
        description='Talks with Sooperlooper',
        epilog='Good luck')
    parser.add_argument("-l", "--load", action="store_true",
                    help="load a session")
    parser.add_argument("-s", "--save", action="store_true",
                        help="save a session")
    parser.add_argument('filename')
    args = parser.parse_args()
    if args.load:
        s.load_session(args.filename)
    if args.save:
        s.save_session(args.filename)
    #time.sleep(1)

def main():
    logging.basicConfig(level=logging.DEBUG)
    s = SLOSC()
    cli(s)
    #s.load_session('/home/poine/Music/jamjo/loops/09_xodo/session.slsess')
    #s.load_session('/home/poine/Music/jamjo/loops/16_all_night_long/session1.slsess')
if __name__ == '__main__':
    main()
