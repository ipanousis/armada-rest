#!/usr/bin/env python

import json
import docker
import requests
import ConfigParser as cp

from flask import Flask

app = Flask(__name__)

config = cp.ConfigParser()
config.readfp(open('cluster.properties','r'))

def get_cluster_name():
  return config.get('default','name')

@app.route('/')
def hello_world():
  return 'Hello World!'

@app.route('/state')
def get_state():
  state = requests.get('http://etcd.%s/v2/keys/?recursive=true' % get_cluster_name()).json()
  nested = state['node']['nodes'][0]
  print 'Number of cluster nodes:', len(nested['nodes'])
  cluster_nodes = nested['nodes']
  containers = []
  for i, node in enumerate(cluster_nodes):
    node_containers = [n['value'] for n in node['nodes']]
    print 'Number of containers on node %d: %d' % (i, len(node_containers))
    containers.extend(node_containers)
  output_state = { 'running_containers' : containers }
  return str(json.dumps(output_state,indent=4))

@app.route('/pull/<image>/<tag>')
def pull_image():
  # use docker client to connect to each node's docker daemon
  # pull the specified image
  return True

if __name__ == '__main__':
  app.run(host='0.0.0.0', debug=True)
