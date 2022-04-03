import nfreezer

import json
from time import sleep
import logging
from pathlib import Path
import sys

host = 'localhost'
user = 'admin'
remotepath = '/Backup'

# mkdir -p Administratif MaisonMarieClaire Emie music OHAPE photo video homes
# python3 /volume1/Divers/dev/src/useful_multimedia_scripts/backup_nas.py
# OSError: [Errno 40] Too many levels of symbolic links: 'Benoit/Documents'


logger = logging.getLogger("download")
formatter = logging.Formatter("%(asctime)s -  %(name)-12s %(levelname)-8s %(message)s")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("/var/services/homes/admin/backup.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.info(f'Starting...')

with open(Path('~/password-backup.json').expanduser()) as json_data_file:
            config = json.load(json_data_file)
encryptionpwd=config["CRYPTO_PASSWORD"]
sftppwd=config["SFTP_PASSWORD"]

if not Path('/volume1/Administratif/AzurRobotix/').is_dir() :
  print("ERROR : please Unlock Administratif")
  logger.error(f' please Unlock Administratif !')
  sleep(5)
if not Path('/volume1/Emie/').is_dir() :
  print("ERROR : please Unlock Emie")
  logger.error(f' please Unlock Emie !')
  sleep(5)
  
folders = ['Administratif', 'Divers', 'Emie', 'homes', 'MaisonMarieClaire', 'OHAPE', 'photo', 'video', 'music']

# Debug
import pysftp
with pysftp.Connection(host, username=user, password=sftppwd) as sftp:
    sftp.cwd('/')
    print('Current dir', sftp.getcwd())
    print('Content', sftp.listdir())
    if sftp.isdir(remotepath):
        sftp.chdir(remotepath)
    else:    
        print(f'Destination directory {remotepath} does not exist.')
# End debug

for folder in folders:
  try:
    logger.info(f'Backuping {folder}')
    # 192.168.0.25 # ./usbshare1-2
    nfreezer.backup(src=f'/volume1/{folder}/', dest=f'{user}@{host}:{remotepath}/benoit/backup-nas/{folder}/',sftppwd=sftppwd,  encryptionpwd=encryptionpwd)
  except:
    msg = f'ERROR with {folder} !\nUnexpected error: {sys.exc_info()}'
    print(msg)
    logger.error(msg)
    continue
  finally:
    print("----------------------------------------------\n")

logger.info(f'Done')

#nfreezer.backup(src='/var/log/', dest='ben@localhost:/tmp/',  encryptionpwd=encryptionpwd)
