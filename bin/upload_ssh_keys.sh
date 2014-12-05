#!/bin/bash

# wait for armada-rest service to start up
sleep 20

rm -rf /root/.ssh/id_rsa* ; ssh-keygen -f /root/.ssh/id_rsa -N ""

NODES=`curl localhost:5000/flocker/state/nodes | egrep -o "([0-9]+\.){3}[0-9]+"`

for NODE in $NODES; do
  sshpass -p kattlefish ssh-copy-id -i /root/.ssh/id_rsa.pub root@$NODE
done

