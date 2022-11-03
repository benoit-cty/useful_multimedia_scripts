#!/bin/bash

# Disk partition to mount
HDD=/dev/sda1
# Folder in the disk partition to store backups
LOCAL_FOLDER=/mnt/data/backup-benoit
# Folder in the container
CT_FOLDER=/mnt/backup-benoit
# Name for the container
CT_NAME=cryptsetup_container

function quit()
{
       echo "Failed !";
       exit 1;
}

if [ ! -d $LOCAL_FOLDER  ];
then
  echo "[ERROR] $LOCAL_FOLDER don't exist !"
  quit;
fi

# Test if container exist
CID=$(docker ps -aq -f status=running -f name=^/${CT_NAME}$)
if [ ! "${CID}" ]; then
  echo "Container doesn't exist, creating it..."
  docker run -d -i -p 22:1979 -v $LOCAL_FOLDER:$CT_FOLDER --name $CT_NAME --privileged --cap-add=ALL ubuntu:22.04
  docker commit $CT_NAME $CT_NAME
  docker start $CT_NAME
  #docker run -d -p 22:1979 -v $LOCAL_FOLDER:$CT_FOLDER --name $CT_NAME --privileged --cap-add=ALL $CT_NAME
  echo "Updating repositories..."
  docker exec $CT_NAME apt update
  #docker exec $CT_NAME apt upgrade
  echo "Installing dependancies..."
  docker exec $CT_NAME apt install -y cryptsetup openssh-server rsync
  echo "Allowing root login into the container..."
  docker exec $CT_NAME sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
fi
unset CID

CID=$(docker ps -q -f status=running -f name=^/${CT_NAME}$)
if [ ! "${CID}" ]; then
  echo "Container not running, starting it..."
  docker start $CT_NAME
fi
unset CID

echo "Starting SSH..."
docker exec $CT_NAME service ssh start
echo "Showing IP address..."
docker inspect $CT_NAME | grep 'IPAddress'
echo "Opening disk..."
docker exec -it $CT_NAME cryptsetup luksOpen $HDD hdd_backup
echo "Mounting disk..."
docker exec $CT_NAME mount -t ext4 /dev/mapper/hdd_backup $CT_FOLDER
echo "When done, run :"
echo " docker exec $CT_NAME umount /dev/mapper/hdd_backup"
echo " docker exec $CT_NAME cryptsetup luksClose hdd_backup"
