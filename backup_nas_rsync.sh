#!/bin/bash

### Priorité faible
PID=$$
renice +19 $PID

DATA_LOCAL=/media/data
BACKUP_DEST=/mnt/data/backup-benoit/backup-beal

#DRY_RUN="--dry-run"
export RSYNC_RSH="ssh -A -J remote_backup_ssh"
REMOTE_SSH="root@172.17.0.3"
RSYNC_OPTIONS="$DRY_RUN --no-perms --no-owner --no-group --delete-after -avz --stats --exclude-from=/home/ben/exclude.txt"
function quit()
{
       echo "Il y a eu des ERREURS. Vous pouvez éteindre le disque.";
       exit 1;
}


if [ -n "$DRY_RUN" ]; then
	echo "=============================================================="
	echo "ATTENTION : Verif en dry-run !!!"
	echo "=============================================================="
fi

function backup()
{
	FOLDER=$1
	FILE_TO_CHECK=$2
	if [ -d $FILE_TO_CHECK  ];
	then
		echo "[INFO] /media/$FOLDER Already mounted"
	else
		mount /media/$FOLDER
		if [ $? -gt 0 ]; then
		    quit;
		fi
		if [ -d $FILE_TO_CHECK  ];
		then
			echo "[INFO] /media/$FOLDER auto mounted"
		else
			quit;
		fi
	fi
	set -x
	rsync $RSYNC_OPTIONS /media/$FOLDER/ $REMOTE_SSH:$BACKUP_DEST/$FOLDER
	set +x
}
backup NAS-Administratif /media/NAS-Administratif/Keypass/
backup NAS-Emie /media/NAS-Emie/Comptes
backup NAS-Divers /media/NAS-Divers/Benoit
backup NAS-Photos /media/NAS-Photos/Photos_2017

