#!/usr/bin/env python3
import logging, os,  shutil
logger = logging.getLogger(__name__)
import xml.etree.ElementTree as ET


def move_sl_session(src, dest, copy_only):
    tree = ET.parse(src)
    root = tree.getroot()
    #print(root)
    src_loop_path, dest_loop_path = [], []
    for child in root:
        #print(child.tag, child.attrib)
        if child.tag == 'Loopers':
            src_loop_path = [_looper.attrib['loop_audio'] for _looper in child]
            dest_loop_path = [os.path.join(dest, os.path.basename(_src_path)) for _src_path in src_loop_path]
            for _looper, _dest_path in zip(child, dest_loop_path):
                _looper.attrib['loop_audio'] = _dest_path               

            #logger.info(f'{src_loop_path}, {dest_loop_path}')
            # copy files
            try: # deate destination directory
                os.mkdir(dest)
                logger.info(f"Directory '{dest}' created successfully.")
            except FileExistsError:
                logger.error(f"Directory '{dest}' already exists.")
            except PermissionError:
                logger.error(f"Permission denied: Unable to create '{dest}'.")
            except Exception as e:
                logger.error(f"An error occurred: {e}")
            for _src, _dest in zip(src_loop_path, dest_loop_path): # copy loops
                logger.info(f"Copying '{_src}' to '{_dest}'.")
                shutil.copyfile(_src, _dest)

    session_dest_path = os.path.join(dest, os.path.basename(src))
    tree.write(session_dest_path)
    logger.info(f"Wrote '{session_dest_path}'.")
            
def main():
    logging.basicConfig(level=logging.INFO)
    src = "/home/poine/Music/tikkelkel/endezihim/session_martha_A.slsess"
    move_sl_session(src, "/tmp/foo", copy_only=True)


if __name__ == '__main__':
    main()
