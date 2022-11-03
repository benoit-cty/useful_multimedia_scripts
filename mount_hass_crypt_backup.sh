#!/bin/bash
# Name you choose for the container
HDD=/dev/sda1
LOCAL_FOLDER=/mnt/data/backup-benoit
CT_FOLDER=/mnt/backup-benoit
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
  docker exec $CT_NAME apt update
  #docker exec $CT_NAME apt upgrade
  docker exec $CT_NAME apt install -y cryptsetup openssh-server rsync
  docker exec $CT_NAME sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
fi
unset CID

CID=$(docker ps -q -f status=running -f name=^/${CT_NAME}$)
if [ ! "${CID}" ]; then
  echo "Container not running, starting it..."
  docker start $CT_NAME
fi
unset CID

docker exec $CT_NAME service ssh start
docker inspect $CT_NAME | grep 'IPAddress'
docker exec -it $CT_NAME cryptsetup luksOpen $HDD hdd_backup
docker exec $CT_NAME mount -t ext4 /dev/mapper/hdd_backup $CT_FOLDER
echo "When done, run :"
echo " docker exec $CT_NAME umount /dev/mapper/hdd_backup"
echo " docker exec $CT_NAME cryptsetup luksClose hdd_backup"
