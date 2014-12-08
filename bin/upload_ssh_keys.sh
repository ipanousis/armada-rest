#!/bin/bash

# wait for armada-rest service to start up
sleep 20

if [[ ! -d /root/.ssh || ! -f /root/.ssh/id_rsa.pub ]] ; then
  mkdir -p /root/.ssh
  ssh-keygen -f /root/.ssh/id_rsa -N ""
fi

NODES=`curl localhost:5000/flocker/state/nodes | egrep -o "([0-9]+\.){3}[0-9]+"`

for NODE in $NODES; do
  sshpass -p kattlefish ssh-copy-id -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa root@$NODE
done

