#!/bin/bash

### Priorité faible
PID=$$
renice +19 $PID

DATA_LOCAL=/media/data
BACKUP_DEST=/media/data/Backup-NAS

#DRY_RUN="--dry-run"
RSYNC_OPTIONS="$DRY_RUN --no-perms --no-owner --no-group --delete-after -avz --stats --exclude-from=/home/ben/exclude.txt"
function quit()
{
       echo "Il y a eu des ERREURS. Vous pouvez éteindre le disque.";
       pico2wave -w /tmp/pico.wav -l fr-FR "Il y a eu une ERREUR Sauvegarde terminé ERREUR ERREUR !" && play /tmp/pico.wav;
       exit 1;
}

#pico2wave -w /tmp/pico.wav -l fr-FR "Bonjour maitre, a votre service !" && play /tmp/pico.wav;

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
	rsync $RSYNC_OPTIONS /media/$FOLDER/ remote_backup_ssh:/media/backup-ben/backup-beal/$FOLDER
}
backup NAS-Administratif /media/NAS-Administratif/Keypass/
backup NAS-Emie /media/NAS-Emie/Comptes
backup NAS-Divers /media/NAS-Divers/Benoit
backup NAS-Photos /media/NAS-Photos/Photos_2017

